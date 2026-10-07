from django import forms
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].strip().lower()

        # Registration must never create an admin/staff account.
        user.is_staff = False
        user.is_superuser = False

        if commit:
            user.save()
        return user

class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30)
    pincode = forms.CharField(
        max_length=6,
        validators=[RegexValidator(r"^[1-9][0-9]{5}$", "Enter a valid six-digit Indian pincode.")],
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "postal-code"}),
    )
    country = forms.CharField(max_length=120)
    state = forms.CharField(max_length=120)
    city = forms.CharField(max_length=120)
    address = forms.CharField(widget=forms.Textarea, max_length=1000)
    shipping_method = forms.ChoiceField(
        choices=[("standard", "Standard delivery"), ("express", "Express delivery")]
    )

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        digits = "".join(character for character in phone if character.isdigit())
        if not 7 <= len(digits) <= 15:
            raise forms.ValidationError("Enter a valid phone number.")
        return phone
