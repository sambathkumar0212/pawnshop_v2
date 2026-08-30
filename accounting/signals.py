from django.db.models.signals import post_save
from django.dispatch import receiver
from transactions.models import Payment, DisbursementTransaction
from branches.models import CashScrollEntry
from .services import post_loan_disbursal_journal, post_loan_repayment_journal, post_bank_deposit_journal


@receiver(post_save, sender=Payment)
def payment_repayment_journal_handler(sender, instance, created, **kwargs):
    """Auto-post double-entry journal whenever a loan repayment is recorded"""
    if instance.loan and instance.amount > 0:
        try:
            post_loan_repayment_journal(instance)
        except Exception:
            pass


@receiver(post_save, sender=DisbursementTransaction)
def disbursal_journal_handler(sender, instance, created, **kwargs):
    """Auto-post double-entry journal whenever a loan disbursal transaction occurs"""
    if instance.loan and instance.amount > 0:
        try:
            post_loan_disbursal_journal(
                loan=instance.loan,
                payment_mode=instance.payment_mode,
                user=instance.disbursed_by,
                bank_ref=instance.bank_reference_number
            )
        except Exception:
            pass


@receiver(post_save, sender=CashScrollEntry)
def scroll_bank_deposit_journal_handler(sender, instance, created, **kwargs):
    """Auto-post double-entry journal whenever a cash remittance to bank is saved"""
    if instance.entry_type == 'BANK_DEPOSIT' and instance.till and instance.amount > 0:
        try:
            post_bank_deposit_journal(instance)
        except Exception:
            pass
