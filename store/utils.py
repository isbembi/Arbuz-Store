import json
import logging
from django.contrib.auth.models import AnonymousUser
from .models import *

logger = logging.getLogger(__name__)


def get_or_create_customer(request):
    """
    Safely return a Customer for authenticated users.

    - If the user is authenticated, return the existing Customer or create one.
    - If the user is anonymous, return None.

    Use this helper everywhere instead of accessing `request.user.customer` directly.
    """
    user = getattr(request, 'user', None)
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return None

    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            'name': getattr(user, 'username', ''),
            'email': getattr(user, 'email', ''),
        }
    )
    if created:
        logger.info(f'Created Customer for user {user.username}')
    return customer


def cookieCart(request):
    cart = request.COOKIES.get('cart', {})
    print("COOOKIES", cart)

    try:
        cart = request.COOKIES['cart']
    except:
        cart = {}

    print('Cart:', cart)
    items = []
    order = {'get_cart_total': 0, 'get_cart_items': 0, 'shipping': False}
    cartItems = order['get_cart_items']

    for i in cart:
        try:
            cartItems += cart[i]['quantity']

            product = Product.objects.get(id=i)
            total = (product.price * cart[i]['quantity'])

            order['get_cart_total'] += total
            order['get_cart_items'] += cart[i]['quantity']

            item = {
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'price': product.price,
                    'imageURL': product.imageURL,
                },
                'quantity': cart[i]['quantity'],
                'get_total': total
            }
            items.append(item)

            if product.digital == False:
                order['shipping'] = True
        except Exception:
            # If an item fails (deleted product, malformed cookie), skip it
            continue
    return {'cartItems': cartItems, 'order': order, 'items': items}

def cartData(request):
    # Prefer the safe helper that ensures a Customer exists for authenticated users
    customer = get_or_create_customer(request)
    if customer is not None:
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        items = order.orderitem_set.all()
        cartItems = order.get_cart_items
    else:
        cookieData = cookieCart(request)
        cartItems = cookieData['cartItems']
        order = cookieData['order']
        items = cookieData['items']
    return {'cartItems': cartItems, 'order': order, 'items': items}