from rest_framework import serializers
from .models import Vendor, Category, Transaction

class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    from_vendor_name = serializers.CharField(source='from_vendor.name', read_only=True, allow_null=True)
    to_vendor_name = serializers.CharField(source='to_vendor.name', read_only=True, allow_null=True)
    from_vendor_gstin = serializers.CharField(source='from_vendor.gstin', read_only=True, allow_null=True)
    to_vendor_gstin = serializers.CharField(source='to_vendor.gstin', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ['transaction_number', 'created_by', 'created_at', 'updated_at']

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
