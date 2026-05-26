from django.contrib import admin
from .models import Vendor, Category, Transaction

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ['name', 'vendor_type', 'phone', 'email', 'is_active', 'created_at']
    list_filter = ['vendor_type', 'is_active']
    search_fields = ['name', 'contact_person', 'phone', 'email']
    ordering = ['name']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'is_active', 'created_at']
    list_filter = ['category_type', 'is_active']
    search_fields = ['name']
    ordering = ['name']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'details', 'category', 'debit_amount', 'credit_amount', 'payment_mode', 'created_by', 'created_at']
    list_filter = ['payment_mode', 'gst_applicable', 'category', 'date']
    search_fields = ['details']
    ordering = ['-date', '-created_at']
    date_hierarchy = 'date'
