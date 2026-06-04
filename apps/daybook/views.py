from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from django.db.models import Sum, Q
from datetime import datetime, timedelta
from apps.accounts.tenant_utils import TenantQuerysetMixin, get_current_company
from .models import Vendor, Category, Transaction
from .serializers import VendorSerializer, CategorySerializer, TransactionSerializer
from .permissions import IsFinanceAdminOrHR

class VendorViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [IsFinanceAdminOrHR]
    filterset_fields = ['vendor_type', 'is_active']
    search_fields = ['name', 'contact_person', 'phone', 'email']
    ordering_fields = ['name', 'created_at']

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = datetime.now()
        instance.save()


class CategoryViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsFinanceAdminOrHR]
    filterset_fields = ['category_type', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        return super().get_queryset()


class TransactionViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
    queryset = Transaction.objects.select_related('category', 'from_vendor', 'to_vendor', 'created_by').all()
    serializer_class = TransactionSerializer
    permission_classes = [IsFinanceAdminOrHR]
    filterset_fields = ['payment_mode', 'gst_applicable', 'category']
    search_fields = ['details', 'from_vendor__name', 'to_vendor__name', 'category__name']
    ordering_fields = ['date', 'created_at']

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = datetime.now()
        instance.save()

    def perform_create(self, serializer):
        company = get_current_company(self.request)
        today = datetime.now()
        date_str = today.strftime('%Y%m%d')
        latest_txn = Transaction.all_objects.filter(
            company=company,
            transaction_number__startswith=f'TXN-{date_str}-'
        ).order_by('-transaction_number').first()

        if latest_txn and latest_txn.transaction_number:
            try:
                seq = int(latest_txn.transaction_number.split('-')[-1])
                new_seq = seq + 1
            except ValueError:
                new_seq = 1
        else:
            new_seq = 1

        txn_number = f'TXN-{date_str}-{new_seq:04d}'

        # Balance tracking is done in the dashboard, but we won't block debit transactions
        # to allow for overdrafts, initial expenses, or credit scenarios.
        
        serializer.save(company=company, created_by=self.request.user, transaction_number=txn_number)

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Date range filter
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        # Vendor filter
        vendor_id = self.request.query_params.get('vendor')
        if vendor_id:
            queryset = queryset.filter(Q(from_vendor_id=vendor_id) | Q(to_vendor_id=vendor_id))
        
        return queryset


@api_view(['GET'])
@permission_classes([IsFinanceAdminOrHR])
def dashboard_summary(request):
    company = get_current_company(request)
    # Get date range from query params or default to current month
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
    
    transactions = Transaction.objects.filter(company=company, date__range=[start_date, end_date])
    
    # Calculate totals including GST
    total_credit = 0
    total_debit = 0
    
    for txn in transactions:
        gst = txn.gst_amount if txn.gst_applicable else 0
        if txn.credit_amount > 0:
            total_credit += txn.credit_amount + gst
        if txn.debit_amount > 0:
            total_debit += txn.debit_amount + gst
    
    balance = total_credit - total_debit
    
    recent_transactions = Transaction.objects.filter(company=company).select_related(
        'category', 'from_vendor', 'to_vendor'
    ).order_by('-date', '-created_at')[:10]
    
    return Response({
        'total_credit': total_credit,
        'total_debit': total_debit,
        'balance': balance,
        'recent_transactions': TransactionSerializer(recent_transactions, many=True).data,
        'start_date': start_date,
        'end_date': end_date,
    })


@api_view(['GET'])
@permission_classes([IsFinanceAdminOrHR])
def vendor_payments_report(request):
    company = get_current_company(request)
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        return Response({'error': 'start_date and end_date required'}, status=400)
    
    transactions = Transaction.objects.filter(
        company=company,
        date__range=[start_date, end_date]
    ).values('to_vendor__name').annotate(
        total_paid=Sum('debit_amount')
    ).order_by('-total_paid')
    
    return Response(list(transactions))


@api_view(['GET'])
@permission_classes([IsFinanceAdminOrHR])
def expense_summary_report(request):
    company = get_current_company(request)
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        return Response({'error': 'start_date and end_date required'}, status=400)
    
    expenses = Transaction.objects.filter(
        company=company,
        date__range=[start_date, end_date],
        debit_amount__gt=0
    ).values('category__name').annotate(
        total=Sum('debit_amount')
    ).order_by('-total')
    
    return Response(list(expenses))


@api_view(['GET'])
@permission_classes([IsFinanceAdminOrHR])
def gst_transactions_report(request):
    company = get_current_company(request)
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    if not start_date or not end_date:
        return Response({'error': 'start_date and end_date required'}, status=400)
    
    transactions = Transaction.objects.filter(
        company=company,
        date__range=[start_date, end_date],
        gst_applicable=True
    ).select_related('category', 'from_vendor', 'to_vendor')
    
    return Response(TransactionSerializer(transactions, many=True).data)


@api_view(['GET'])
@permission_classes([IsFinanceAdminOrHR])
def monthly_report(request):
    company = get_current_company(request)
    year = int(request.query_params.get('year', datetime.now().year))
    month = int(request.query_params.get('month', datetime.now().month))
    
    start_date = f"{year}-{month:02d}-01"
    
    # Calculate last day of month
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    transactions = Transaction.objects.filter(company=company, date__range=[start_date, end_date])
    
    # Calculate totals including GST
    total_credit = 0
    total_debit = 0
    
    for txn in transactions:
        gst = txn.gst_amount if txn.gst_applicable else 0
        if txn.credit_amount > 0:
            total_credit += txn.credit_amount + gst
        if txn.debit_amount > 0:
            total_debit += txn.debit_amount + gst
    
    category_wise = transactions.values('category__name', 'category__category_type').annotate(
        total_debit=Sum('debit_amount'),
        total_credit=Sum('credit_amount')
    )
    
    return Response({
        'year': year,
        'month': month,
        'total_credit': total_credit,
        'total_debit': total_debit,
        'balance': total_credit - total_debit,
        'category_wise': list(category_wise),
        'transaction_count': transactions.count(),
    })
