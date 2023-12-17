from django.shortcuts import render, redirect
from django.core import serializers
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.template import loader
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import Material, Supplier, BomProduct, BomMaterial
from .forms import SupplierForm
import json
from django.urls import reverse

# Import your Xero integration functions
from .xero_integration import get_xero_oauth2_session, get_invoices

def xero_data_view(request):
    # Check if we're receiving the callback from Xero with the authorization code
    code = request.GET.get('code')
    if code:
        # Fetch the token with the authorization code
        token = fetch_xero_token(code)
        oauth_session = OAuth2Session(CLIENT_ID, token=token)
    else:
        # If no code is present, start the authorization flow
        oauth_session = get_xero_oauth2_session()
        authorization_url, state = oauth_session.authorization_url("https://login.xero.com/identity/connect/authorize")
        return HttpResponseRedirect(authorization_url)

    # Fetch the invoices
    try:
        invoices = get_invoices(oauth_session)
    except Exception as e:
        return HttpResponse(f"Error fetching invoices: {e}")

    # Render the response
    return render(request, 'xero_data.html', {'invoices': invoices})

def testing_view(request):
    materials = Material.objects.all()
    bom_products = BomProduct.objects.values_list('product_name', flat=True)
    bom_materials = BomMaterial.objects.select_related('material').all()  # Preload all BomMaterial objects

    context = {
        'materials': materials,
        'bom_products': bom_products,
        'bom_materials': bom_materials,  # Add bom_materials to the context
    }
    return render(request, 'testing.html', context)

@csrf_exempt  # This is for simplicity; in production, you should use CSRF tokens
def update_bom_materials(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            for item in data:
                bom_material = BomMaterial.objects.get(id=item['id'])
                bom_material.quantity = item['quantity']
                bom_material.save()
            return JsonResponse({"status": "success"}, status=200)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)


def main(request):
    template = loader.get_template('main.html')
    context = {
    }
    return HttpResponse(template.render(context, request))

def master_rates(request):
    materials_list= Material.objects.all().values()
    suppliers_list=Supplier.objects.all().values('id', 'supplier')
    template = loader.get_template('master_rates.html')
    context = {
       'materials_list': materials_list,
       'suppliers_list': suppliers_list,
    }
    return HttpResponse(template.render(context, request))

def suppliers(request):
    suppliers_list= Supplier.objects.all().values()
    template = loader.get_template('suppliers.html')
    context = {
       'suppliers_list': suppliers_list,
    }
    return HttpResponse(template.render(context, request))

def supplier_view(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('suppliers.html')  # Replace with your success URL
    else:
        form = SupplierForm()

    return render(request, 'suppliers.html', {'form': form})

def save_supplier(request):
    try:
        data = json.loads(request.body)
        supplier = Supplier(
            supplier=data['supplier'],
            contact=data['contact'],
            email=data['email'],
            phone=data['phone']
        )
        supplier.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    
def update_supplier(request):
    try:
        data = json.loads(request.body)
        # Fetch the supplier object based on the ID
        supplier_obj = Supplier.objects.get(id=data['id'])
        # Update the fields
        supplier_obj.supplier = data['supplier']
        supplier_obj.contact = data['contact']
        supplier_obj.email = data['email']
        supplier_obj.phone = data['phone']
        supplier_obj.save()
        return JsonResponse({'status': 'success'})
    except Supplier.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Supplier not found'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    
def delete_supplier(request):
    try:
        data = json.loads(request.body)
        supplier_obj = Supplier.objects.get(id=data['id'])
        supplier_obj.delete()
        return JsonResponse({'status': 'success'})
    except Supplier.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Supplier not found'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    
def update_material_rate(request):
    try:
        data = json.loads(request.body)
        material = Material.objects.get(pk=data['id'])
        material.material = data['material']
        material.units = data['units']
        material.rate = data['rate']

        # Assuming `supplier` in Material is a CharField and stores the name
        material.supplier = data['supplier']  # Directly using the supplier's name

        material.save()
        return JsonResponse({'status': 'success', 'message': 'Material rate updated successfully.'})
    except Material.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Material not found.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@require_POST
def delete_material_rate(request):
    try:
        data = json.loads(request.body)
        material_id = data.get('id')
        material = Material.objects.get(pk=material_id)
        material.delete()
        return JsonResponse({'status': 'success', 'message': 'Material rate deleted successfully.'})
    except Material.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Material not found.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@require_POST
def save_material_rate(request):
    try:
        data = json.loads(request.body)
        # Create a new Material object
        new_material = Material(
            material=data['material'],
            units=data['units'],
            rate=data['rate'],
            supplier=data['supplier']
        )
        new_material.save()
        return JsonResponse({'status': 'success', 'message': 'Material rate saved successfully.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

def bom_view(request):
    products = BomProduct.objects.all()
    materials = Material.objects.all()
    all_materials = Material.objects.all()
    all_materials_json = serializers.serialize('json', all_materials)
    product_materials = {product.id: BomMaterial.objects.filter(product=product) for product in products}

    # Create a dictionary of products indexed by their IDs
    products_dict = {product.id: product for product in products}

    return render(request, 'bom.html', {
        'products_dict': products_dict,
        'materials': materials,
        'all_materials_json': all_materials_json,
        'product_materials': product_materials
    })

@require_POST
def save_materials(request):
    try:
        data = json.loads(request.body)
        product_id = data['productId']
        materials_data = data['materials']

        for item in materials_data:
            material_name = item['material']
            quantity = item['quantity']
            # Logic to update or create BomMaterial instances

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})