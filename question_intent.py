"""Narrow deterministic budget guards for explicit visual and procedural questions.

Other phrasing still uses the model's tool routing. These guards do not decide
whether to retrieve documentation or live data, or introduce a second model call.
"""
import re


def requires_visual_evidence(question):
    return bool(re.search(r'\b(?:icons?|layout|look like)\b|\bwhere\b.{0,80}\b(?:button|dropdown|control|toolbar)\b|图标|布局|按钮.{0,20}(?:位置|在哪|哪里)|(?:哪里|哪儿|在哪).{0,20}(?:按钮|控件)', question, re.IGNORECASE))


def is_text_only_question(question):
    if requires_visual_evidence(question):
        return False
    return bool(re.search(r'\b(?:how (?:do|can|to|many|much)|what steps|required fields|which fields)\b|如何|怎样|怎么|步骤|多少|几张', question, re.IGNORECASE))
