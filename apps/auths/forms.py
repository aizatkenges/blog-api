from django.core.exceptions import ValidationError
from unfold.forms import UserChangeForm, UserCreationForm

from apps.auths.models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name")

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower()

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")

        return email


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"
