from django.contrib import admin
from .models import Report, ReportSchedule, ReportExecution, Dashboard, DashboardWidget


class ReportScheduleInline(admin.TabularInline):
    model = ReportSchedule
    extra = 0


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'created_by', 'is_public', 'created_at')
    list_filter = ('report_type', 'is_public', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_by', 'created_at')
    inlines = [ReportScheduleInline]
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('report', 'frequency', 'time_of_day', 'is_active', 'last_run')
    list_filter = ('frequency', 'is_active')
    search_fields = ('report__name', 'email_subject')
    filter_horizontal = ('recipients',)


@admin.register(ReportExecution)
class ReportExecutionAdmin(admin.ModelAdmin):
    list_display = ('report', 'executed_by', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'start_time')
    search_fields = ('report__name',)
    readonly_fields = ('report', 'schedule', 'executed_by', 'parameters_used', 'start_time', 'end_time', 'status', 'result_file', 'error_message')


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 1


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'is_public', 'is_default', 'created_at')
    list_filter = ('is_public', 'is_default', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_by', 'created_at')
    inlines = [DashboardWidgetInline]
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ('title', 'dashboard', 'widget_type', 'chart_type')
    list_filter = ('widget_type', 'chart_type')
    search_fields = ('title', 'dashboard__name')
