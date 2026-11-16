from django import forms

from .content import FEEDBACK_CATEGORIES


class FeedbackForm(forms.Form):
    """The only fields we store. The template draws the controls (topic cards, 1-5 scale)."""

    category = forms.ChoiceField(
        choices=FEEDBACK_CATEGORIES,
        initial="question",
        widget=forms.RadioSelect,
    )
    message = forms.CharField(
        max_length=2000,
        error_messages={"required": "Write a message before sending."},
        widget=forms.Textarea,
    )
    rating = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(1, 6)],
        coerce=int,
        required=False,
        empty_value=None,
        widget=forms.RadioSelect,
    )
