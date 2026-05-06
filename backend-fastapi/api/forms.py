from datetime import date, timedelta

from django import forms

from api.models import CheckoutOrder, FarmStory, Product, Recipe, Review

PRODUCT_STATUS_CHOICES = [
    ("Available", "Available"),
    ("In Season", "In Season"),
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

ACCOUNT_TYPE_CHOICES = [
    ("individual", "Individual"),
    ("community_group", "Community Group"),
    ("restaurant", "Restaurant"),
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
    account_type = forms.ChoiceField(
        choices=ACCOUNT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs=_select_class),
    )
    organization_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={**_field_class, "placeholder": "Organisation name"}),
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
    # Override so the field is optional — it defaults to 5 on the model.
    # The add-product form only shows basic fields and never submits this.
    low_stock_threshold = forms.IntegerField(
        required=False,
        min_value=1,
        initial=5,
        widget=forms.NumberInput(attrs={**_field_class, "min": "1"}),
        help_text="Alert when stock falls to or below this level.",
    )

    class Meta:
        model = Product
        fields = [
            "name", "category", "description", "price", "stock",
            "allergens", "is_organic", "discount_percentage",
            "harvest_date", "season_start", "season_end", "low_stock_threshold",
        ]
        widgets = {
            "name": forms.TextInput(attrs={**_field_class, "placeholder": "Product name"}),
            "category": forms.TextInput(attrs={**_field_class, "placeholder": "e.g. Vegetable"}),
            "description": forms.Textarea(attrs={**_field_class, "rows": 3, "placeholder": "Describe your product..."}),
            "price": forms.NumberInput(attrs={**_field_class, "step": "0.01", "min": "0"}),
            "stock": forms.NumberInput(attrs={**_field_class, "min": "0"}),
            "allergens": forms.TextInput(attrs={**_field_class, "placeholder": "e.g. Milk, Eggs, Gluten (leave blank if none)"}),
            "is_organic": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "discount_percentage": forms.NumberInput(attrs={**_field_class, "min": "0", "max": "50", "placeholder": "0"}),
            "harvest_date": forms.DateInput(attrs={**_field_class, "type": "date"}),
            "season_start": forms.DateInput(attrs={**_field_class, "type": "date"}),
            "season_end": forms.DateInput(attrs={**_field_class, "type": "date"}),
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

    def clean_discount_percentage(self):
        discount = self.cleaned_data.get("discount_percentage")
        if discount is not None and not (0 <= discount <= 50):
            raise forms.ValidationError("Discount must be between 0% and 50%.")
        return discount


class ProductEditForm(ProductForm):
    """Form used when editing an existing product in the producer UI.

    Exposes a normalized `status` choice to the producer (business-facing
    labels: 'in season', 'out of season', 'unavailable'). The view maps
    these to the underlying DB status values.
    """
    STATUS_CHOICES = [
        ("in season", "in season"),
        ("out of season", "out of season"),
        ("unavailable", "unavailable"),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=True,
        widget=forms.Select(attrs=_select_class),
        label="Status",
    )


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "title", "text"]
        widgets = {
            "rating": forms.Select(attrs=_select_class),
            "title": forms.TextInput(attrs={**_field_class, "placeholder": "Summary of your review"}),
            "text": forms.Textarea(attrs={**_field_class, "rows": 3, "placeholder": "Tell us more..."}),
        }


class CheckoutForm(forms.ModelForm):
    accept_terms = forms.BooleanField(
        required=True,
        error_messages={"required": "You must accept the terms and conditions."},
    )

    class Meta:
        model = CheckoutOrder
        # delivery_date is omitted — each producer has its own delivery date
        # submitted as delivery_date_<producer_id> POST fields handled in the view.
        fields = ["full_name", "email", "address", "city", "postal_code", "payment_method", "special_instructions"]
        widgets = {
            "full_name": forms.TextInput(attrs={**_field_class, "placeholder": "Full name"}),
            "email": forms.EmailInput(attrs={**_field_class, "placeholder": "Email address"}),
            "address": forms.TextInput(attrs={**_field_class, "placeholder": "Street address"}),
            "city": forms.TextInput(attrs={**_field_class, "placeholder": "City"}),
            "postal_code": forms.TextInput(attrs={**_field_class, "placeholder": "Postal code"}),
            "payment_method": forms.Select(
                choices=PAYMENT_METHOD_CHOICES, attrs=_select_class
            ),
            "special_instructions": forms.Textarea(attrs={**_field_class, "rows": 3, "placeholder": "Bulk delivery notes, dietary requirements, access instructions…"}),
        }

    def validate_email(self, value):
        if "@" not in value:
            raise forms.ValidationError("Enter a valid email address.")
        return value


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ["title", "description", "ingredients", "instructions", "seasonal_tag"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "ingredients": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "One ingredient per line"}),
            "instructions": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "seasonal_tag": forms.Select(attrs={"class": "form-select"}),
        }


class FarmStoryForm(forms.ModelForm):
    class Meta:
        model = FarmStory
        fields = ["title", "content"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


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
