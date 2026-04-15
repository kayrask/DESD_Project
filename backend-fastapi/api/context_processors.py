def cart_context(request):
    """Inject cart_count into every template so the navbar badge stays current."""
    cart = request.session.get("cart", [])
    cart_count = sum(int(i.get("quantity", 0)) for i in cart)
    return {"cart_count": cart_count}
