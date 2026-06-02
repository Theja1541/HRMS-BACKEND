from rest_framework import serializers
from apps.accounts.tenant_utils import get_current_company
from .models import Vendor, Category, Transaction, TransactionItem

class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'
        read_only_fields = ['company', 'created_at', 'updated_at']

    def validate(self, data):
        request = self.context.get('request')
        company = get_current_company(request)
        name = data.get('name')
        
        if name:
            qs = Vendor.objects.filter(company=company, name__iexact=name)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError({"name": "A vendor with this name already exists for your company."})
        return data


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['company', 'created_at', 'updated_at']

    def validate(self, data):
        request = self.context.get('request')
        company = get_current_company(request)
        name = data.get('name')
        
        if name:
            qs = Category.objects.filter(company=company, name__iexact=name)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError({"name": "A category with this name already exists for your company."})
        return data


class TransactionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionItem
        fields = '__all__'
        read_only_fields = ['transaction', 'created_at']


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    from_vendor_name = serializers.CharField(source='from_vendor.name', read_only=True, allow_null=True)
    to_vendor_name = serializers.CharField(source='to_vendor.name', read_only=True, allow_null=True)
    from_vendor_gstin = serializers.CharField(source='from_vendor.gstin', read_only=True, allow_null=True)
    to_vendor_gstin = serializers.CharField(source='to_vendor.gstin', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    items = TransactionItemSerializer(many=True, required=False)

    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ['company', 'transaction_number', 'created_by', 'created_at', 'updated_at']

    def validate(self, data):
        debit = data.get('debit_amount') or 0
        credit = data.get('credit_amount') or 0
        
        if debit == 0 and credit == 0:
            raise serializers.ValidationError("Either debit or credit amount must be provided")
        
        if debit > 0 and credit > 0:
            raise serializers.ValidationError("Cannot have both debit and credit amounts")

        payment_mode = data.get('payment_mode')
        if payment_mode == 'BANK':
            if not data.get('bank_name') or not data.get('account_number'):
                raise serializers.ValidationError("Bank name and Account number are required for BANK payment mode")
        elif payment_mode == 'UPI':
            if not data.get('upi_id'):
                raise serializers.ValidationError("UPI ID is required for UPI payment mode")
        elif payment_mode == 'CHEQUE':
            if not data.get('cheque_number'):
                raise serializers.ValidationError("Cheque number is required for CHEQUE payment mode")

        gst_applicable = data.get('gst_applicable', False)
        if gst_applicable and not data.get('gst_amount'):
            raise serializers.ValidationError("GST amount is required if GST is applicable")

        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        transaction = super().create(validated_data)
        for item_data in items_data:
            TransactionItem.objects.create(transaction=transaction, **item_data)
        return transaction

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        transaction = super().update(instance, validated_data)
        
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                TransactionItem.objects.create(transaction=transaction, **item_data)
                
        return transaction
