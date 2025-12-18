from django.shortcuts import render, redirect
from .models import *
from django.http import JsonResponse
import json
import datetime
import logging

from .utils import cookieCart, cartData, get_or_create_customer
from .forms import UserRegisterForm, UserLoginForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

# Set up logging for debugging
logger = logging.getLogger(__name__)


def store(request):
    if request.user.is_authenticated:
        customer, created = Customer.objects.get_or_create(
            user=request.user,
            defaults={
                'name': request.user.username,
                'email': request.user.email,
            }
        )
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        items = order.orderitem_set.all()
    else:
        items = []
        order = {'get_cart_total': 0, 'get_cart_items': 0}

    products = Product.objects.all()

    context = {
        'products': products,
        'items': items,
        'order': order,
    }
    return render(request, 'store/store.html', context)


def cart(request):
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']

    context = {'items': items, 'order': order, 'cartItems': cartItems}
    return render(request, 'store/cart.html', context)


def checkout(request):
    """
    Checkout page view (requires authentication).
    
    - Checks if user is authenticated
    - Redirects to login if not
    - Shows checkout form to authenticated users
    """
    if not request.user.is_authenticated:
        return redirect('login')
    
    data = cartData(request)
    cartItems = data['cartItems']
    order = data['order']
    items = data['items']

    context = {'items': items, 'order': order, 'cartItems': cartItems}
    return render(request, 'store/checkout.html', context)


def updateItem(request):
    """
    AJAX endpoint to update cart items (add/remove).
    
    Expects JSON:
    - productId: product ID
    - action: 'add' or 'remove'
    
    Only works for authenticated users.
    """
    try:
        data = json.loads(request.body)
        productId = data['productId']
        action = data['action']

        logger.info(f'Update cart - Action: {action}, Product: {productId}')

        # Only authenticated users can update cart
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)

        # Safely retrieve or create Customer
        customer = get_or_create_customer(request)
        if customer is None:
            return JsonResponse({'error': 'Customer profile unavailable'}, status=400)
        product = Product.objects.get(id=productId)
        order, created = Order.objects.get_or_create(customer=customer, complete=False)

        orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

        if action == 'add':
            orderItem.quantity = (orderItem.quantity + 1)
            logger.info(f'Item added - Product: {product.name}, New quantity: {orderItem.quantity}')
        elif action == 'remove':
            orderItem.quantity = (orderItem.quantity - 1)
            logger.info(f'Item removed - Product: {product.name}, New quantity: {orderItem.quantity}')

        orderItem.save()

        if orderItem.quantity <= 0:
            orderItem.delete()
            logger.info(f'Item deleted from cart - Product: {product.name}')

        return JsonResponse('Item updated', safe=False)
    
    except Product.DoesNotExist:
        logger.error(f'Product not found: {productId}')
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        logger.error(f'Error updating cart: {str(e)}')
        return JsonResponse({'error': 'Error updating cart'}, status=400)


def productDetail(request, item):
    data = cartData(request)
    cartItems = data['cartItems']
    product = Product.objects.get(id=item)
    context = {'cartItems': cartItems, 'product': product}
    return render(request, 'store/productDetail.html', context)


def clearCart(request):
    orderItems = OrderItem.objects.all()

    orderItems.delete()
    data = cartData(request)
    cartItems = data['cartItems']

    products = Product.objects.all()
    context = {'products': products, 'cartItems': cartItems}
    return render(request, 'store/store.html', context)

def processOrder(request):
    logger.info(f'Processing order: {request.body}')
    transaction_id = datetime.datetime.now().timestamp()
    data = json.loads(request.body)

    if request.user.is_authenticated:
        # Ensure a Customer exists for this user
        customer = get_or_create_customer(request)
        if customer is None:
            logger.error('Authenticated user but customer could not be obtained')
            return JsonResponse({'error': 'Customer profile unavailable'}, status=400)
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
        total = float(data['form']['total'])
        order.transaction_id = transaction_id

        if total == order.get_cart_total:
            order.complete = True
        order.save()

        if order.shipping == True:
            ShippingAddress.objects.create(
                customer=customer,
                order=order,
                address=data['shipping']['address'],
                city=data['shipping']['city'],
                state=data['shipping']['state'],
                zipcode=data['shipping']['zipcode'],
            )
        logger.info(f'Order {order.id} completed successfully')
    else:
        logger.warning('Unauthenticated user attempted checkout')
    return JsonResponse('Payment complete', safe=False)


# ==================== AUTHENTICATION VIEWS ====================

def register(request):
    """
    User registration view.
    
    GET: Display registration form
    POST: Process registration form
         - Create new User account
         - Create associated Customer profile
         - Automatically log in the user
    """
    if request.user.is_authenticated:
        return redirect('store')
    
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # Create the User object
            user = form.save()
            
            # Create associated Customer profile
            Customer.objects.create(
                user=user,
                name=user.username,
                email=user.email
            )
            
            # Automatically log in the user after registration
            login(request, user)
            logger.info(f'New user registered: {user.username}')
            return redirect('store')
        else:
            # Form has errors, pass them to template
            context = {'form': form}
            return render(request, 'store/register.html', context)
    else:
        form = UserRegisterForm()
    
    context = {'form': form}
    return render(request, 'store/register.html', context)


def login_view(request):
    """
    User login view.
    
    GET: Display login form
    POST: Process login form
         - Authenticate user with username/password
         - Create session for user
         - Redirect to store or next page
    """
    if request.user.is_authenticated:
        return redirect('store')
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            # Authenticate user
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # Log in the user (creates session)
                login(request, user)
                logger.info(f'User logged in: {username}')
                
                # Redirect to 'next' page if specified, otherwise store
                next_page = request.GET.get('next', 'store')
                return redirect(next_page)
            else:
                # Authentication failed
                form.add_error(None, 'Invalid username or password.')
                logger.warning(f'Failed login attempt for username: {username}')
    else:
        form = UserLoginForm()
    
    context = {'form': form}
    return render(request, 'store/login.html', context)


def logout_view(request):
    """
    User logout view.
    
    GET: Log out the user and redirect to store
    - Destroys user session
    - Clears authentication
    """
    logout(request)
    logger.info(f'User logged out: {request.user}')
    return redirect('store')


@login_required(login_url='login')
def profile(request):
    """
    User profile/dashboard view (requires login).
    
    Shows:
    - User account information
    - Order history
    - Account settings option
    """
    # Use safe helper (will create Customer if missing)
    customer = get_or_create_customer(request)
    orders = customer.order_set.all() if customer is not None else []
    
    context = {
        'customer': customer,
        'orders': orders,
    }
    return render(request, 'store/profile.html', context)
