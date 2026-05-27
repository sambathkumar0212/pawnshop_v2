from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Report(models.Model):
    """Model for saved custom reports"""
    REPORT_TYPES = [
        ('sales', 'Sales Report'),
        ('inventory', 'Inventory Report'),
        ('loans', 'Loan Report'),
        ('payments', 'Payment Report'),
        ('customer', 'Customer Report'),
        ('branch', 'Branch Performance'),
        ('staff', 'Staff Performance'),
        ('financial', 'Financial Report'),
        ('custom', 'Custom Report'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    parameters = models.JSONField(default=dict)
    query_definition = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports')
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('report')
        verbose_name_plural = _('reports')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"


class ReportSchedule(models.Model):
    """Schedule for automated report generation"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ]
    
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='schedules')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    day_of_week = models.IntegerField(null=True, blank=True, help_text=_('0=Monday, 6=Sunday'))
    day_of_month = models.IntegerField(null=True, blank=True)
    time_of_day = models.TimeField()
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='report_subscriptions')
    email_subject = models.CharField(max_length=200)
    email_body = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('report schedule')
        verbose_name_plural = _('report schedules')
    
    def __str__(self):
        return f"Schedule for {self.report.name} ({self.get_frequency_display()})"


class ReportExecution(models.Model):
    """Log of report executions"""
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failure', 'Failure'),
        ('in_progress', 'In Progress'),
    ]
    
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='executions')
    schedule = models.ForeignKey(ReportSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='executions')
    executed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    parameters_used = models.JSONField(default=dict)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    result_file = models.FileField(upload_to='report_results/', null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = _('report execution')
        verbose_name_plural = _('report executions')
        ordering = ['-start_time']
    
    def __str__(self):
        return f"Execution of {self.report.name} at {self.start_time}"


class Dashboard(models.Model):
    """Custom dashboard model"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dashboards')
    is_public = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('dashboard')
        verbose_name_plural = _('dashboards')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class DashboardWidget(models.Model):
    """Widget for custom dashboards"""
    WIDGET_TYPES = [
        ('chart', 'Chart'),
        ('metric', 'Metric'),
        ('table', 'Table'),
        ('list', 'List'),
        ('map', 'Map'),
        ('custom', 'Custom'),
    ]
    
    CHART_TYPES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('area', 'Area Chart'),
        ('scatter', 'Scatter Plot'),
    ]
    
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name='widgets')
    title = models.CharField(max_length=100)
    widget_type = models.CharField(max_length=10, choices=WIDGET_TYPES)
    chart_type = models.CharField(max_length=10, choices=CHART_TYPES, null=True, blank=True)
    data_source = models.JSONField(default=dict)
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)
    width = models.IntegerField(default=1)
    height = models.IntegerField(default=1)
    refresh_interval = models.IntegerField(null=True, blank=True, help_text=_('Refresh interval in minutes'))
    
    class Meta:
        verbose_name = _('dashboard widget')
        verbose_name_plural = _('dashboard widgets')
        ordering = ['dashboard', 'position_y', 'position_x']
    
    def __str__(self):
        return f"{self.title} on {self.dashboard.name}"
