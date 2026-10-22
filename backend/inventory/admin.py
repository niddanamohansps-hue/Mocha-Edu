from django.contrib import admin

from .models import Item, ItemCategory, StockLevel, StockLocation, StockMovement

# Tenant data is managed through the API and its audit trail, not the (public-schema) admin site.
