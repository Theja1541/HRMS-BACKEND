import os
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
from apps.billing.models import GSTInvoice, PaymentTransaction
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io
import logging

logger = logging.getLogger(__name__)

class InvoiceService:
    """Manages GST calculations, invoice sequential numbering, and ReportLab PDF drawing."""

    def generate_invoice_number(self):
        """Generates a sequential invoice number like INV-2026-0001."""
        year = timezone.now().year
        # Count existing invoices of current year
        count = GSTInvoice.objects.filter(issued_at__year=year).count() + 1
        return f"INV-{year}-{str(count).padStart(4, '0')}" if hasattr(str, 'padStart') else f"INV-{year}-{str(count).zfill(4)}"

    def create_gst_invoice(self, transaction):
        """
        Creates a GSTInvoice database entry and compiles a professional ReportLab PDF,
        storing it into the transaction's GSTInvoice.
        """
        try:
            if hasattr(transaction, "gst_invoice"):
                logger.info(f"GST Invoice already exists for transaction: {transaction.id}")
                return transaction.gst_invoice

            company = transaction.company
            subtotal = transaction.amount
            gst_percentage = Decimal("18.00")
            gst_amount = transaction.gst_amount
            total = transaction.total_amount

            invoice_number = self.generate_invoice_number()

            # Create the GSTInvoice entry first
            invoice = GSTInvoice.objects.create(
                invoice_number=invoice_number,
                company=company,
                payment_transaction=transaction,
                gst_percentage=gst_percentage,
                gst_amount=gst_amount,
                subtotal=subtotal,
                total=total,
                issued_at=timezone.now(),
            )

            # Generate ReportLab PDF in memory
            pdf_buffer = io.BytesIO()
            self._draw_invoice_pdf(invoice, pdf_buffer)
            pdf_buffer.seek(0)

            # Save the PDF to the FileField
            file_name = f"{invoice_number}.pdf"
            invoice.invoice_pdf.save(file_name, ContentFile(pdf_buffer.read()))
            invoice.save()

            # Update the transaction's invoice number too for tracking
            transaction.invoice_number = invoice_number
            transaction.save(update_fields=["invoice_number"])

            logger.info(f"Successfully generated GST Invoice {invoice_number} for Company {company.name}")
            return invoice

        except Exception as e:
            logger.error(f"Failed to generate invoice for transaction {transaction.id}: {str(e)}")
            raise e

    def _draw_invoice_pdf(self, invoice, buffer):
        """Draws a professional GST Tax Invoice PDF using ReportLab."""
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()
        
        # Define clean, professional color palette
        primary_color = colors.HexColor("#1e3a8a")  # Sleek Navy Blue
        dark_text = colors.HexColor("#334155")      # Charcoal
        light_grey = colors.HexColor("#f8fafc")     # Slate backgrounds
        border_grey = colors.HexColor("#cbd5e1")    # Subtle borders

        # Custom Paragraph styles
        title_style = ParagraphStyle(
            "InvoiceTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=primary_color,
            spaceAfter=15
        )
        subtitle_style = ParagraphStyle(
            "InvoiceSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.HexColor("#475569"),
            spaceAfter=5
        )
        regular_style = ParagraphStyle(
            "InvoiceRegular",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=dark_text,
            leading=13
        )
        bold_style = ParagraphStyle(
            "InvoiceBold",
            parent=regular_style,
            fontName="Helvetica-Bold"
        )
        header_cell_style = ParagraphStyle(
            "HeaderCell",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.white,
            alignment=0
        )

        story = []

        # 1. Header Table (Invoice Logo Placeholder / Name & Core metadata)
        header_data = [
            [
                Paragraph("TAX INVOICE", title_style),
                Paragraph(f"<b>Invoice No:</b> {invoice.invoice_number}<br/><b>Date:</b> {invoice.issued_at.strftime('%d-%b-%Y')}", regular_style)
            ]
        ]
        header_table = Table(header_data, colWidths=[320, 210])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT')
        ]))
        story.append(header_table)
        story.append(Spacer(1, 15))

        from apps.superadmin.models import SystemSetting
        def get_setting(key, default):
            try:
                setting = SystemSetting.objects.filter(key=key).first()
                return setting.value if setting and setting.value else default
            except Exception:
                return default

        platform_name = get_setting("platform_name", "HRMS SaaS Platforms Ltd")
        platform_address = get_setting("platform_address", "Sector 62, Noida, Uttar Pradesh, 201301")
        platform_state = get_setting("platform_state", "Uttar Pradesh")
        platform_gstin = get_setting("platform_gstin", "09AAAAA1111A1Z1 (Uttar Pradesh)")
        platform_email = get_setting("support_email", "support@hrmsaas.com")
        platform_phone = get_setting("platform_phone", "06301989372")

        seller_details = (
            f"<b>SOLD BY:</b><br/>"
            f"{platform_name}<br/>"
            f"{platform_address}<br/>"
            f"<b>State:</b> {platform_state}<br/>"
            f"<b>GSTIN:</b> {platform_gstin}<br/>"
            f"<b>Email:</b> {platform_email}<br/>"
            f"<b>Phone:</b> {platform_phone}"
        )

        buyer_details = (
            f"<b>BILLED TO:</b><br/>"
            f"{invoice.company.name}<br/>"
            f"{invoice.company.address or 'N/A'}<br/>"
            f"<b>State:</b> {invoice.company.state or 'N/A'} (Code: {invoice.company.state_code or 'N/A'})<br/>"
            f"<b>GSTIN:</b> {invoice.company.gstin or 'N/A'}<br/>"
            f"<b>Phone:</b> {invoice.company.phone or 'N/A'}"
        )

        details_data = [
            [
                Paragraph(seller_details, regular_style),
                Paragraph(buyer_details, regular_style)
            ]
        ]
        details_table = Table(details_data, colWidths=[260, 270])
        details_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, -1), light_grey),
            ('BOX', (0, 0), (-1, -1), 0.5, border_grey),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(details_table)
        story.append(Spacer(1, 20))

        # 3. Items and GST Calculation Breakdown Table
        plan = invoice.payment_transaction.subscription.subscription_plan if invoice.payment_transaction.subscription else None
        plan_name = plan.name if plan else "SaaS Subscription Plan"
        billing_cycle = invoice.payment_transaction.subscription.billing_cycle.capitalize() if invoice.payment_transaction.subscription else "Monthly"

        # Item list headers
        items_data = [
            [
                Paragraph("Description", header_cell_style),
                Paragraph("Billing", header_cell_style),
                Paragraph("GST Rate", header_cell_style),
                Paragraph("Subtotal", header_cell_style),
                Paragraph("Total", header_cell_style),
            ],
            [
                Paragraph(f"<b>{plan_name} Subscription</b><br/><font color='#64748b'>Multi-tenant HRMS Modules access</font>", regular_style),
                Paragraph(billing_cycle, regular_style),
                Paragraph(f"{invoice.gst_percentage}%", regular_style),
                Paragraph(f"INR {invoice.subtotal:,.2f}", regular_style),
                Paragraph(f"INR {invoice.total:,.2f}", regular_style),
            ]
        ]

        items_table = Table(items_data, colWidths=[200, 70, 70, 95, 95])
        items_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
            ('BOX', (0, 0), (-1, -1), 0.5, border_grey),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, border_grey),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 20))

        # 4. GST Breakup calculations (CGST + SGST or IGST)
        cgst_rate = invoice.gst_percentage / 2
        sgst_rate = invoice.gst_percentage / 2
        cgst_amt = invoice.gst_amount / 2
        sgst_amt = invoice.gst_amount / 2

        # Draw a beautiful summary totals card
        totals_data = [
            [Paragraph("<b>Subtotal:</b>", regular_style), Paragraph(f"INR {invoice.subtotal:,.2f}", regular_style)],
            [Paragraph(f"<b>CGST ({cgst_rate}%):</b>", regular_style), Paragraph(f"INR {cgst_amt:,.2f}", regular_style)],
            [Paragraph(f"<b>SGST ({sgst_rate}%):</b>", regular_style), Paragraph(f"INR {sgst_amt:,.2f}", regular_style)],
            [Paragraph("<font size='10' color='#1e3a8a'><b>Grand Total:</b></font>", regular_style), Paragraph(f"<font size='10' color='#1e3a8a'><b>INR {invoice.total:,.2f}</b></font>", bold_style)]
        ]

        totals_table = Table(totals_data, colWidths=[150, 120])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, -1), (1, -1), 1.5, primary_color),
            ('BACKGROUND', (0, 0), (-1, -1), light_grey),
            ('BOX', (0, 0), (-1, -1), 0.5, border_grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))

        # Place the totals table in a layout to right align it
        layout_data = [["", totals_table]]
        layout_table = Table(layout_data, colWidths=[260, 270])
        layout_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT')
        ]))
        story.append(layout_table)
        story.append(Spacer(1, 40))

        # 5. Footer terms & Declaration
        footer_text = (
            "<b>Terms & Conditions:</b><br/>"
            "1. This is a computer-generated GST invoice and requires no physical signature.<br/>"
            "2. Subscription fees are billed in advance and are non-refundable.<br/>"
            f"3. For billing disputes, please contact {platform_email} within 7 days of receipt.<br/>"
            "<br/><br/>"
            "<center>Thank you for choosing HRMS SaaS! We appreciate your business.</center>"
        )
        story.append(Paragraph(footer_text, regular_style))

        # Build document
        doc.build(story)
