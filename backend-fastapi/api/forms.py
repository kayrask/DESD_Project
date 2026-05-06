from datetime import date, timedelta

from django import forms

from api.models import CheckoutOrder, FarmStory, Product, Recipe, Review, User

# UK Food Standards Agency 14 regulated allergens
ALLERGEN_CHOICES = [
    ("Celery", "Celery"),
    ("Gluten", "Gluten (wheat, rye, barley, oats)"),
    ("Crustaceans", "Crustaceans (prawns, crab, lobster)"),
    ("Eggs", "Eggs"),
    ("Fish", "Fish"),
    ("Lupin", "Lupin"),
    ("Milk", "Milk"),
    ("Molluscs", "Molluscs (mussels, oysters)"),
    ("Mustard", "Mustard"),
    ("Nuts", "Nuts (almonds, hazelnuts, walnuts, cashews)"),
    ("Peanuts", "Peanuts"),
    ("Sesame", "Sesame"),
    ("Soya", "Soya"),
    ("Sulphites", "Sulphur dioxide / sulphites"),
]

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
    remember_me = forms.BooleanField(required=False)


class RegisterForm(forms.Form):
    full_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={**_field_class, "placeholder": "Full name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={**_field_class, "placeholder": "Email address"})
    )
    phone = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={**_field_class, "placeholder": "Phone number (optional)"}),
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
    postal_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={**_field_class, "placeholder": "e.g. BS1 4DJ"}),
    )

    def clean_postal_code(self):
        pc = self.cleaned_data.get("postal_code", "").strip().upper()
        return pc

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
        if cleaned.get("role") == "producer" and not cleaned.get("postal_code"):
            self.add_error("postal_code", "Postcode is required for producers.")
        return cleaned


class ProductForm(forms.ModelForm):
    # Override so the field is optional — it defaults to 5 on the model.
    low_stock_threshold = forms.IntegerField(
        required=False,
        min_value=1,
        initial=5,
        widget=forms.NumberInput(attrs={**_field_class, "min": "1"}),
        help_text="Alert when stock falls to or below this level.",
    )

    # Replace free-text allergens with standardised multi-select checkboxes.
    # Stored as a comma-separated string in the existing TextField.
    allergens = forms.MultipleChoiceField(
        choices=ALLERGEN_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-select checkboxes from the stored comma-separated string
        if self.instance and self.instance.pk and self.instance.allergens:
            stored = [a.strip() for a in self.instance.allergens.split(",") if a.strip()]
            self.fields["allergens"].initial = stored

    def clean_allergens(self):
        values = self.cleaned_data.get("allergens") or []
        return ", ".join(sorted(values))

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


class AccountSettingsForm(forms.Form):
    full_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={**_field_class, "placeholder": "Full name"}),
    )
    phone = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={**_field_class, "placeholder": "Phone number (optional)"}),
    )
    postal_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={**_field_class, "placeholder": "e.g. BS1 4DJ"}),
    )
    # Password change — all optional; only validated when new_password is provided
    current_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={**_field_class, "placeholder": "Current password"}),
    )
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={**_field_class, "placeholder": "New password (8+ chars)"}),
    )
    confirm_new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={**_field_class, "placeholder": "Confirm new password"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_postal_code(self):
        return self.cleaned_data.get("postal_code", "").strip().upper()

    def clean(self):
        cleaned = super().clean()
        new_pw = cleaned.get("new_password")
        confirm = cleaned.get("confirm_new_password")
        current = cleaned.get("current_password")

        if new_pw:
            if not current:
                self.add_error("current_password", "Enter your current password to set a new one.")
            elif self.user and not self.user.check_password(current):
                self.add_error("current_password", "Incorrect current password.")
            if len(new_pw) < 8:
                self.add_error("new_password", "Must be at least 8 characters.")
            elif not any(c.isupper() for c in new_pw):
                self.add_error("new_password", "Must contain at least one uppercase letter.")
            elif not any(c.islower() for c in new_pw):
                self.add_error("new_password", "Must contain at least one lowercase letter.")
            elif not any(c.isdigit() for c in new_pw):
                self.add_error("new_password", "Must contain at least one digit.")
            if confirm and new_pw != confirm:
                self.add_error("confirm_new_password", "Passwords do not match.")

        if self.user and self.user.role == "producer" and not cleaned.get("postal_code"):
            self.add_error("postal_code", "Postcode is required for producers.")

        return cleaned
