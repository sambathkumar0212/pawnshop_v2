from django.contrib import admin
from .models import AccountHead, JournalEntry, JournalItem


class JournalItemInline(admin.TabularInline):
    model = JournalItem
    extra = 2


@admin.register(AccountHead)
class AccountHeadAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'branch', 'is_active']
    list_filter = ['category', 'is_active', 'branch']
    search_fields = ['code', 'name']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['entry_number', 'date', 'branch', 'reference_type', 'reference_id', 'total_debit', 'total_credit']
    list_filter = ['reference_type', 'date', 'branch']
    search_fields = ['entry_number', 'reference_id', 'narration']
    inlines = [JournalItemInline]
