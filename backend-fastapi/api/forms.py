from datetime import date, timedelta

from django import forms

from api.models import CheckoutOrder, Product

PRODUCT_STATUS_CHOICES = [
    ("Available", "Available"),
    ("Out of Stock", "Out of Stock"),
    ("Unavailable", "Unavailable"),
]

ORDER_STATUS_CHOICES = [
    ("Pending", "Pending"),
    ("Confirmed", "Confirmed"),
    ("Ready", "Ready"),
    ("Delivered", "Delivered"),
]

ROLE_CHOICES = [
    ("customer", "Customer"),
    ("producer", "Producer"),
]

PAYMENT_METHOD_CHOICES = [
    ("card", "Credit / Debit Card"),
    ("bank_transfer", "Bank Transfer"),
    ("cash", "Cash on Delivery"),
]

_field_class = {"class": "form-control"}
_select_class = {"class": "form-select"}


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={**_field_class, "placeholder": "Email address", "autofocus": True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={**_field_class, "placeholder": "Password"})
    )


class RegisterForm(forms.Form):
    full_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={**_field_class, "placeholder": "Full name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={**_field_class, "placeholder": "Email address"})
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={**_field_class, "placeholder": "Password (8+ chars)"}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={**_field_class, "placeholder": "Confirm password"})
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs=_select_class),
    )

    def clean_password(self):
        password = self.cleaned_data.get("password", "")
        if not any(c.isupper() for c in password):
            raise forms.ValidationError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in password):
            raise forms.ValidationError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in password):
            raise forms.ValidationError("Password must contain at least one digit.")
        return password

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get("password")
        cpw = cleaned.get("confirm_password")
        if pw and cpw and pw != cpw:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "category", "price", "stock", "status"]
        widgets = {
            "name": forms.TextInput(attrs={**_field_class, "placeholder": "Product name"}),
            "category": forms.TextInput(attrs={**_field_class, "placeholder": "e.g. Vegetable"}),
            "price": forms.NumberInput(attrs={**_field_class, "step": "0.01", "min": "0"}),
            "stock": forms.NumberInput(attrs={**_field_class, "min": "0"}),
            "status": forms.Select(attrs=_select_class),
        }

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is not None and price < 0:
            raise forms.ValidationError("Price must be zero or greater.")
        return price

    def clean_stock(self):
        stock = self.cleaned_data.get("stock")
        if stock is not None and stock < 0:
            raise forms.ValidationError("Stock must be zero or greater.")
        return stock


class CheckoutForm(forms.ModelForm):
    accept_terms = forms.BooleanField(
        required=True,
        error_messages={"required": "You must accept the terms and conditions."},
    )

    class Meta:
        model = CheckoutOrder
        fields = ["full_name", "email", "address", "city", "postal_code", "payment_method", "delivery_date"]
        widgets = {
            "full_name": forms.TextInput(attrs={**_field_class, "placeholder": "Full name"}),
            "email": forms.EmailInput(attrs={**_field_class, "placeholder": "Email address"}),
            "address": forms.TextInput(attrs={**_field_class, "placeholder": "Street address"}),
            "city": forms.TextInput(attrs={**_field_class, "placeholder": "City"}),
            "postal_code": forms.TextInput(attrs={**_field_class, "placeholder": "Postal code"}),
            "payment_method": forms.Select(
                choices=PAYMENT_METHOD_CHOICES, attrs=_select_class
            ),
            "delivery_date": forms.DateInput(attrs={**_field_class, "type": "date"}),
        }

    def validate_email(self, value):
        if "@" not in value:
            raise forms.ValidationError("Enter a valid email address.")
        return value

    def clean_delivery_date(self):
        delivery_date = self.cleaned_data.get("delivery_date")
        if delivery_date is not None:
            min_date = date.today() + timedelta(days=2)
            if delivery_date < min_date:
                raise forms.ValidationError(
                    "Delivery date must be at least 2 days from today."
                )
        return delivery_date


class OrderStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=ORDER_STATUS_CHOICES,
        widget=forms.Select(attrs=_select_class),
    )


class ReportFilterForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={**_field_class, "type": "date"}),
        label="From",
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={**_field_class, "type": "date"}),
        label="To",
    )

    def clean(self):
        cleaned = super().clean()
        d_from = cleaned.get("date_from")
        d_to = cleaned.get("date_to")
        if d_from and d_to and d_from > d_to:
            raise forms.ValidationError("'From' date must be before 'To' date.")
        return cleaned
