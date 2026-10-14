from unittest.mock import Mock
from scripts.evaluate_manual import evaluate, estimated_cost


def test_evaluation_detects_wrong_versions_and_unnecessary_vision_without_claiming_accuracy():
    session = Mock(); response = Mock(); session.post.return_value = response
    response.status_code = 200; response.headers = {'Content-Type': 'application/json'}
    response.json.return_value = {'answer': 'Steps', 'sources': [{'section_id': 'add-card', 'version': 'old'}],
        'metrics': {'vision': {'status': 'used', 'version': 'old'}, 'manual_version': 'old'}}
    report = evaluate('https://chat.example', [{'id': 'T', 'kind': 'text', 'question': 'Create a card', 'chapters': ['add-card']}], session=session, expected_version='new')
    assert report['structural_passed'] == 0
    assert report['human_accuracy_review'] == 'pending'
    assert report['results'][0]['problems'] == ['source-version-mismatch', 'unnecessary-vision-call']
    assert report['results'][0]['estimated_model_usd'] is None


def test_cost_requires_actual_usage_and_explicit_prices_for_all_calls():
    metrics = {'generation': [{'prompt_tokens': 1000, 'completion_tokens': 100}],
        'vision': {'status': 'used', 'prompt_tokens': 1000, 'completion_tokens': 100}}
    assert estimated_cost(metrics, {}) is None
    assert estimated_cost(metrics, {'text_input': 1, 'text_output': 2, 'vision_input': 3, 'vision_output': 4}) == 0.0046
