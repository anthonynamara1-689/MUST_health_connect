from django import forms

from .models import Event, Location


class IssueStockForm(forms.Form):
    item = forms.IntegerField(min_value=1)
    location = forms.IntegerField(min_value=1)
    event = forms.IntegerField(min_value=1, required=False)
    quantity = forms.IntegerField(min_value=1, max_value=10000)
    # Demo switch on the stock page: crash on purpose after the UPDATE to show ROLLBACK.
    simulate_crash = forms.BooleanField(required=False)


class EventForm(forms.ModelForm):
    """'Plan an event' dialog on the staff Events page. The ORM writes the INSERT."""

    class Meta:
        model = Event
        fields = ["title", "activity", "event_date", "location", "is_public", "description"]
        widgets = {"event_date": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "activity": "Budget line",
            "event_date": "Date",
            "is_public": "Show on the student site",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = Location.objects.order_by("name")
        self.fields["location"].empty_label = "Choose a place"
        self.fields["activity"].empty_label = "Choose a budget line"
        self.fields["description"].required = False
