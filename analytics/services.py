from django.db.models import Avg, Sum, Count, Q, F
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
import logging

from .models import RiskProfile, LoanPrediction, CashFlowForecast, MarketIndicator, RiskAlert, BusinessExpense, ExpenseCategory
from accounts.models import Customer
from transactions.models import Loan, Payment
from branches.models import Branch

logger = logging.getLogger(__name__)


class RiskAnalytics:
    """
    Advanced Risk Analytics service for predictive analysis and business intelligence
    """
    
    def __init__(self):
        self.model_version = "1.0"
        self.risk_weights = {
            'payment_history': 0.35,
            'loan_to_value': 0.25,
            'demographic': 0.15,
            'economic_indicator': 0.15,
            'behavioral': 0.10
        }
    
    def calculate_default_risk(self, customer_profile: Customer, loan_details: Dict = None) -> Dict:
        """
        Calculate comprehensive default risk score for a customer
        
        Args:
            customer_profile: Customer instance
            loan_details: Optional dict with loan amount, duration, etc.
            
        Returns:
            Dict with risk score, level, and detailed breakdown
        """
        try:
            # Get or create risk profile
            risk_profile, created = RiskProfile.objects.get_or_create(
                customer=customer_profile,
                defaults={'risk_score': 50.0, 'risk_level': 'medium'}
            )
            
            # Calculate individual risk components
            payment_score = self._calculate_payment_history_score(customer_profile)
            ltv_score = self._calculate_loan_to_value_score(customer_profile, loan_details)
            demographic_score = self._calculate_demographic_score(customer_profile)
            economic_score = self._calculate_economic_indicator_score()
            behavioral_score = self._calculate_behavioral_score(customer_profile)
            
            # Calculate weighted risk score
            total_score = (
                payment_score * self.risk_weights['payment_history'] +
                ltv_score * self.risk_weights['loan_to_value'] +
                demographic_score * self.risk_weights['demographic'] +
                economic_score * self.risk_weights['economic_indicator'] +
                behavioral_score * self.risk_weights['behavioral']
            )
            
            # Determine risk level
            risk_level = self._determine_risk_level(total_score)
            
            # Update risk profile
            risk_profile.risk_score = total_score
            risk_profile.risk_level = risk_level
            risk_profile.payment_history_score = payment_score
            risk_profile.loan_to_value_score = ltv_score
            risk_profile.demographic_score = demographic_score
            risk_profile.economic_indicator_score = economic_score
            risk_profile.behavioral_score = behavioral_score
            risk_profile.calculation_version = self.model_version
            risk_profile.save()
            
            # Create risk alert if necessary
            if risk_level in ['high', 'very_high']:
                self._create_risk_alert(customer_profile, total_score, risk_level)
            
            return {
                'customer_id': customer_profile.id,
                'risk_score': float(total_score),
                'risk_level': risk_level,
                'components': {
                    'payment_history': float(payment_score),
                    'loan_to_value': float(ltv_score),
                    'demographic': float(demographic_score),
                    'economic_indicator': float(economic_score),
                    'behavioral': float(behavioral_score)
                },
                'recommendation': self._get_risk_recommendation(risk_level, total_score)
            }
            
        except Exception as e:
            logger.error(f"Error calculating default risk for customer {customer_profile.id}: {str(e)}")
            return {'error': str(e), 'risk_score': 50.0, 'risk_level': 'medium'}
    
    def _calculate_payment_history_score(self, customer: Customer) -> Decimal:
        """Calculate payment history score (0-100, lower is better)"""
        loans = customer.loans.all()
        
        if not loans.exists():
            return Decimal('50.0')  # Neutral score for new customers
        
        total_loans = loans.count()
        defaulted_loans = loans.filter(status='defaulted').count()
        overdue_loans = loans.filter(
            status='active',
            due_date__lt=timezone.now().date()
        ).count()
        
        # Calculate payment efficiency
        payments = Payment.objects.filter(loan__customer=customer)
        if payments.exists():
            delay_days = 0  # Simplified calculation
        else:
            delay_days = 0
        
        # Score calculation (lower is better)
        default_penalty = (defaulted_loans / total_loans) * 40 if total_loans > 0 else 0
        overdue_penalty = (overdue_loans / total_loans) * 20 if total_loans > 0 else 0
        delay_penalty = min(delay_days * 0.5, 20)  # Max 20 points for delays
        
        score = default_penalty + overdue_penalty + delay_penalty
        return Decimal(str(min(score, 100.0)))
    
    def _calculate_loan_to_value_score(self, customer: Customer, loan_details: Dict = None) -> Decimal:
        """Calculate loan-to-value ratio score"""
        recent_loans = customer.loans.filter(
            created_at__gte=timezone.now() - timedelta(days=365)
        ).order_by('-created_at')[:5]  # Last 5 loans
        
        if not recent_loans.exists():
            return Decimal('25.0')  # Low risk for new customers
        
        # Calculate average LTV ratio
        ltv_ratios = []
        for loan in recent_loans:
            if hasattr(loan, 'loanitem_set') and loan.loanitem_set.exists():
                loan_item = loan.loanitem_set.first()
                if loan_item and loan_item.market_price_22k and loan_item.net_weight:
                    estimated_value = loan_item.market_price_22k * loan_item.net_weight
                    if estimated_value > 0:
                        ltv_ratio = float(loan.principal_amount) / float(estimated_value)
                        ltv_ratios.append(ltv_ratio)
        
        if not ltv_ratios:
            return Decimal('25.0')
        
        avg_ltv = sum(ltv_ratios) / len(ltv_ratios)
        
        # Convert LTV to risk score (higher LTV = higher risk)
        if avg_ltv <= 0.5:
            score = 10.0
        elif avg_ltv <= 0.7:
            score = 25.0
        elif avg_ltv <= 0.85:
            score = 50.0
        else:
            score = 80.0
        
        return Decimal(str(score))
    
    def _calculate_demographic_score(self, customer: Customer) -> Decimal:
        """Calculate demographic-based risk score"""
        score = 25.0  # Base score
        
        # Customer tenure factor
        tenure_days = (timezone.now().date() - customer.created_at.date()).days
        if tenure_days > 365:
            score -= 10.0  # Long-term customers get lower risk
        elif tenure_days < 30:
            score += 15.0  # New customers get higher risk
        
        # Location factor (if city/state available)
        if customer.city and customer.state:
            # Metro cities might have different risk profiles
            metro_cities = ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Kolkata', 'Hyderabad']
            if customer.city in metro_cities:
                score -= 5.0  # Slightly lower risk in metro cities
        
        return Decimal(str(max(0.0, min(score, 100.0))))
    
    def _calculate_economic_indicator_score(self) -> Decimal:
        """Calculate score based on current economic indicators"""
        current_date = timezone.now().date()
        
        # Get recent economic indicators
        gold_price = MarketIndicator.objects.filter(
            indicator_type='gold_price',
            date__gte=current_date - timedelta(days=30)
        ).order_by('-date').first()
        
        inflation_rate = MarketIndicator.objects.filter(
            indicator_type='inflation_rate',
            date__gte=current_date - timedelta(days=90)
        ).order_by('-date').first()
        
        score = 25.0  # Base economic risk
        
        # Gold price volatility factor
        if gold_price:
            # High gold prices might indicate market instability
            if gold_price.value > Decimal('55000'):  # Above average gold price
                score += 10.0
        
        # Inflation factor
        if inflation_rate:
            if inflation_rate.value > Decimal('6.0'):  # High inflation
                score += 15.0
            elif inflation_rate.value < Decimal('2.0'):  # Very low inflation
                score += 5.0
        
        return Decimal(str(min(score, 100.0)))
    
    def _calculate_behavioral_score(self, customer: Customer) -> Decimal:
        """Calculate behavioral risk score based on customer interactions"""
        score = 25.0  # Base behavioral score
        
        # Loan frequency analysis
        loans_last_year = customer.loans.filter(
            created_at__gte=timezone.now() - timedelta(days=365)
        ).count()
        
        if loans_last_year > 6:  # Very frequent borrower
            score += 20.0
        elif loans_last_year > 3:  # Frequent borrower
            score += 10.0
        elif loans_last_year == 0:  # Inactive customer
            score += 15.0
        
        # Loan amount pattern analysis
        recent_loans = customer.loans.order_by('-created_at')[:5]
        if recent_loans.count() >= 3:
            amounts = [float(loan.principal_amount) for loan in recent_loans]
            # Check for increasing loan amounts (might indicate financial stress)
            if len(amounts) >= 3 and amounts[0] > amounts[1] > amounts[2]:
                score += 15.0
        
        return Decimal(str(min(score, 100.0)))
    
    def _determine_risk_level(self, score: Decimal) -> str:
        """Determine risk level based on score"""
        if score <= 20:
            return 'very_low'
        elif score <= 35:
            return 'low'
        elif score <= 55:
            return 'medium'
        elif score <= 75:
            return 'high'
        else:
            return 'very_high'
    
    def _get_risk_recommendation(self, risk_level: str, score: float) -> str:
        """Get recommendation based on risk level"""
        recommendations = {
            'very_low': "Excellent customer. Consider offering premium rates and higher loan amounts.",
            'low': "Low-risk customer. Standard processing with favorable terms.",
            'medium': "Moderate risk. Apply standard verification and monitoring procedures.",
            'high': "High-risk customer. Require additional documentation and closer monitoring.",
            'very_high': "Very high risk. Consider rejecting or requiring additional security/guarantor."
        }
        return recommendations.get(risk_level, "Review customer profile carefully.")
    
    def _create_risk_alert(self, customer: Customer, score: Decimal, risk_level: str):
        """Create risk alert for high-risk customers"""
        RiskAlert.objects.get_or_create(
            customer=customer,
            alert_type='high_risk_customer',
            status='active',
            defaults={
                'severity': 'high' if risk_level == 'high' else 'critical',
                'title': f'High Risk Customer Alert - {customer.full_name}',
                'description': f'Customer {customer.full_name} has been assessed with {risk_level} risk (score: {score})',
                'recommendation': self._get_risk_recommendation(risk_level, float(score)),
                'actual_value': score
            }
        )
    
    def predict_cash_flow(self, branch_id: int, time_period: str = 'monthly', periods_ahead: int = 3) -> List[Dict]:
        """
        Forecast cash flow for better liquidity management
        
        Args:
            branch_id: Branch ID to forecast for
            time_period: 'daily', 'weekly', 'monthly', or 'quarterly'
            periods_ahead: Number of periods to forecast
            
        Returns:
            List of cash flow predictions
        """
        try:
            branch = Branch.objects.get(id=branch_id)
            current_date = timezone.now().date()
            
            forecasts = []
            
            for i in range(1, periods_ahead + 1):
                forecast_date = self._calculate_forecast_date(current_date, time_period, i)
                
                # Predict each component (simplified for now)
                predicted_disbursements = self._predict_loan_disbursements(branch, time_period, i)
                predicted_repayments = self._predict_loan_repayments(branch, time_period, i)
                predicted_interest = self._predict_interest_income(branch, time_period, i)
                predicted_fees = self._predict_fee_income(branch, time_period, i)
                predicted_sales = self._predict_sales_revenue(branch, time_period, i)
                predicted_expenses = self._predict_operating_expenses(branch, time_period, i)
                
                # Calculate net cash flow
                net_cash_flow = (
                    predicted_repayments + predicted_interest + predicted_fees + predicted_sales
                    - predicted_disbursements - predicted_expenses
                )
                
                # Apply seasonal adjustments
                seasonal_factor = self._calculate_seasonal_factor(forecast_date, time_period)
                trend_factor = self._calculate_trend_factor(i)
                
                adjusted_net_cash_flow = net_cash_flow * (1 + seasonal_factor + trend_factor)
                
                # Calculate confidence level
                confidence = self._calculate_forecast_confidence(i)
                
                # Create or update forecast record
                forecast, created = CashFlowForecast.objects.update_or_create(
                    branch=branch,
                    forecast_date=forecast_date,
                    forecast_type=time_period,
                    defaults={
                        'predicted_loan_disbursements': predicted_disbursements,
                        'predicted_loan_repayments': predicted_repayments,
                        'predicted_interest_income': predicted_interest,
                        'predicted_fee_income': predicted_fees,
                        'predicted_sales_revenue': predicted_sales,
                        'predicted_operating_expenses': predicted_expenses,
                        'predicted_net_cash_flow': adjusted_net_cash_flow,
                        'confidence_level': confidence,
                        'seasonal_adjustment': seasonal_factor * 100,
                        'trend_adjustment': trend_factor * 100,
                        'model_version': self.model_version
                    }
                )
                
                forecasts.append({
                    'date': forecast_date,
                    'period': i,
                    'disbursements': float(predicted_disbursements),
                    'repayments': float(predicted_repayments),
                    'interest_income': float(predicted_interest),
                    'fee_income': float(predicted_fees),
                    'sales_revenue': float(predicted_sales),
                    'operating_expenses': float(predicted_expenses),
                    'net_cash_flow': float(adjusted_net_cash_flow),
                    'confidence_level': float(confidence),
                    'seasonal_adjustment': float(seasonal_factor * 100),
                    'trend_adjustment': float(trend_factor * 100)
                })
                
                # Create cash flow alerts if necessary
                if adjusted_net_cash_flow < 0:
                    self._create_cash_flow_alert(branch, forecast_date, adjusted_net_cash_flow)
            
            return forecasts
            
        except Exception as e:
            logger.error(f"Error predicting cash flow for branch {branch_id}: {str(e)}")
            return [{'error': str(e)}]
    
    def _calculate_forecast_date(self, current_date: date, time_period: str, periods_ahead: int) -> date:
        """Calculate the forecast date based on time period"""
        if time_period == 'daily':
            return current_date + timedelta(days=periods_ahead)
        elif time_period == 'weekly':
            return current_date + timedelta(weeks=periods_ahead)
        elif time_period == 'monthly':
            return current_date + timedelta(days=periods_ahead * 30)
        elif time_period == 'quarterly':
            return current_date + timedelta(days=periods_ahead * 90)
        else:
            return current_date + timedelta(days=periods_ahead * 30)
    
    def _predict_loan_disbursements(self, branch: Branch, time_period: str, period: int) -> Decimal:
        """Predict loan disbursements for the period"""
        recent_loans = branch.loans.filter(
            created_at__gte=timezone.now() - timedelta(days=90)
        )
        
        if recent_loans.exists():
            avg_monthly_disbursement = recent_loans.aggregate(
                total=Sum('principal_amount')
            )['total'] / 3  # 3 months average
            
            # Apply seasonal factor
            seasonal_factor = self._calculate_seasonal_factor(
                self._calculate_forecast_date(timezone.now().date(), time_period, period),
                time_period
            )
            
            # Convert to Decimal to avoid type mismatch
            avg_disbursement_decimal = Decimal(str(float(avg_monthly_disbursement or 0)))
            seasonal_multiplier = Decimal('1') + seasonal_factor
            
            return avg_disbursement_decimal * seasonal_multiplier
        
        return Decimal('0')
    
    def _predict_loan_repayments(self, branch: Branch, time_period: str, period: int) -> Decimal:
        """Predict loan repayments for the period"""
        active_loans = branch.loans.filter(status='active')
        total_expected = Decimal('0')
        
        for loan in active_loans:
            remaining_balance = getattr(loan, 'remaining_balance', loan.principal_amount)
            if remaining_balance > 0:
                payment_probability = self._estimate_payment_probability(loan, period)
                # Convert payment_probability to Decimal to avoid type mismatch
                probability_decimal = Decimal(str(payment_probability))
                expected_payment = Decimal(str(float(remaining_balance))) * probability_decimal
                total_expected += expected_payment
        
        return total_expected
    
    def _predict_interest_income(self, branch: Branch, time_period: str, period: int) -> Decimal:
        """Predict interest income for the period"""
        active_loans = branch.loans.filter(status='active')
        total_interest = Decimal('0')
        
        for loan in active_loans:
            if loan.scheme and loan.principal_amount:
                monthly_interest_rate = Decimal(str(float(loan.scheme.interest_rate))) / Decimal('12') / Decimal('100')
                # Calculate monthly interest on distribution amount (amount customer received)
                monthly_interest = loan.distribution_amount * monthly_interest_rate
                
                if time_period == 'monthly':
                    total_interest += monthly_interest
                elif time_period == 'quarterly':
                    total_interest += monthly_interest * Decimal('3')
                elif time_period == 'weekly':
                    total_interest += monthly_interest / Decimal('4')
                elif time_period == 'daily':
                    total_interest += monthly_interest / Decimal('30')
        
        return total_interest
    
    def _predict_fee_income(self, branch: Branch, time_period: str, period: int) -> Decimal:
        """Predict fee income for the period"""
        recent_fees = Payment.objects.filter(
            loan__branch=branch,
            payment_date__gte=timezone.now().date() - timedelta(days=90),
            notes__icontains='processing fee'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        avg_monthly_fees = Decimal(str(float(recent_fees))) / Decimal('3')
        
        if time_period == 'monthly':
            return avg_monthly_fees
        elif time_period == 'quarterly':
            return avg_monthly_fees * Decimal('3')
        elif time_period == 'weekly':
            return avg_monthly_fees / Decimal('4')
        elif time_period == 'daily':
            return avg_monthly_fees / Decimal('30')
        
        return avg_monthly_fees
    
    def _predict_sales_revenue(self, branch: Branch, time_period: str, period: int) -> Decimal:
        """Predict sales revenue for the period"""
        try:
            from transactions.models import Sale
            
            recent_sales = Sale.objects.filter(
                branch=branch,
                sale_date__gte=timezone.now().date() - timedelta(days=90)
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            
            avg_monthly_sales = Decimal(str(float(recent_sales))) / Decimal('3')
            
            if time_period == 'monthly':
                return avg_monthly_sales
            elif time_period == 'quarterly':
                return avg_monthly_sales * Decimal('3')
            elif time_period == 'weekly':
                return avg_monthly_sales / Decimal('4')
            elif time_period == 'daily':
                return avg_monthly_sales / Decimal('30')
            
            return avg_monthly_sales
        except ImportError:
            return Decimal('0')
    
    def _predict_operating_expenses(self, branch: Branch, time_period: str, period: int) -> Decimal:
        """Predict operating expenses for the period"""
        estimated_monthly_expenses = Decimal('50000')  # Base estimate
        
        # Adjust based on branch size
        if hasattr(branch, 'staff'):
            staff_count = branch.staff.count()
            staff_multiplier = Decimal(str(max(1, staff_count)))
            estimated_monthly_expenses *= staff_multiplier
        
        if time_period == 'monthly':
            return estimated_monthly_expenses
        elif time_period == 'quarterly':
            return estimated_monthly_expenses * Decimal('3')
        elif time_period == 'weekly':
            return estimated_monthly_expenses / Decimal('4')
        elif time_period == 'daily':
            return estimated_monthly_expenses / Decimal('30')
        
        return estimated_monthly_expenses
    
    def _calculate_seasonal_factor(self, forecast_date: date, time_period: str) -> Decimal:
        """Calculate seasonal adjustment factor"""
        month = forecast_date.month
        
        # Festival seasons (higher gold demand/lending)
        if month in [10, 11, 12, 4]:  # Diwali, Akshaya Tritiya seasons
            return Decimal('0.15')  # 15% increase
        elif month in [1, 5]:  # Post-festival, wedding season
            return Decimal('0.10')  # 10% increase
        elif month in [6, 7, 8]:  # Monsoon season (typically lower activity)
            return Decimal('-0.05')  # 5% decrease
        else:
            return Decimal('0.0')  # No adjustment
    
    def _calculate_trend_factor(self, period: int) -> Decimal:
        """Calculate trend adjustment factor"""
        base_growth = Decimal('0.02')  # 2% monthly growth
        return base_growth * Decimal(str(period))
    
    def _calculate_forecast_confidence(self, period: int) -> Decimal:
        """Calculate confidence level for forecast"""
        base_confidence = Decimal('85.0')
        confidence_decay = Decimal('5.0') * Decimal(str(period - 1))
        return max(Decimal('50.0'), base_confidence - confidence_decay)
    
    def _estimate_payment_probability(self, loan, period: int) -> float:
        """Estimate probability of payment for a loan in given period"""
        days_since_issue = (timezone.now().date() - loan.issue_date).days
        days_to_due = (loan.due_date - timezone.now().date()).days
        
        if days_to_due <= 30:  # Due soon
            return 0.7
        elif days_to_due <= 90:  # Due in medium term
            return 0.4
        else:  # Long term
            return 0.2
    
    def _create_cash_flow_alert(self, branch: Branch, forecast_date: date, predicted_amount: Decimal):
        """Create cash flow alert for negative predictions"""
        RiskAlert.objects.get_or_create(
            branch=branch,
            alert_type='cash_flow_warning',
            status='active',
            defaults={
                'severity': 'high' if predicted_amount < -100000 else 'medium',
                'title': f'Negative Cash Flow Predicted - {branch.name}',
                'description': f'Negative cash flow of ₹{abs(predicted_amount):,.2f} predicted for {forecast_date}',
                'recommendation': 'Review loan disbursement policies and ensure adequate liquidity.',
                'actual_value': predicted_amount
            }
        )
    
    def analyze_seasonal_patterns(self, branch_id: int = None) -> Dict:
        """Analyze seasonal demand patterns across the business"""
        try:
            loans_query = Loan.objects.all()
            if branch_id:
                loans_query = loans_query.filter(branch_id=branch_id)
            
            # Group loans by month
            monthly_data = {}
            for month in range(1, 13):
                month_loans = loans_query.filter(created_at__month=month)
                monthly_data[month] = {
                    'count': month_loans.count(),
                    'total_amount': float(month_loans.aggregate(total=Sum('principal_amount'))['total'] or 0),
                    'average_amount': float(month_loans.aggregate(avg=Avg('principal_amount'))['avg'] or 0)
                }
            
            # Identify peak and low seasons
            peak_month = max(monthly_data.items(), key=lambda x: x[1]['total_amount'])
            low_month = min(monthly_data.items(), key=lambda x: x[1]['total_amount'])
            
            return {
                'monthly_patterns': monthly_data,
                'peak_season': {
                    'month': peak_month[0],
                    'total_amount': peak_month[1]['total_amount'],
                    'loan_count': peak_month[1]['count']
                },
                'low_season': {
                    'month': low_month[0],
                    'total_amount': low_month[1]['total_amount'],
                    'loan_count': low_month[1]['count']
                },
                'seasonality_index': peak_month[1]['total_amount'] / low_month[1]['total_amount'] if low_month[1]['total_amount'] > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing seasonal patterns: {str(e)}")
            return {'error': str(e)}
    
    def get_portfolio_health_metrics(self, branch_id: int = None) -> Dict:
        """Get comprehensive portfolio health metrics"""
        try:
            loans_query = Loan.objects.all()
            if branch_id:
                loans_query = loans_query.filter(branch_id=branch_id)
            
            total_loans = loans_query.count()
            active_loans = loans_query.filter(status='active').count()
            defaulted_loans = loans_query.filter(status='defaulted').count()
            
            # Calculate portfolio metrics
            default_rate = (defaulted_loans / total_loans * 100) if total_loans > 0 else 0
            
            # Average loan amount
            avg_loan_amount = loans_query.aggregate(avg=Avg('principal_amount'))['avg'] or 0
            
            # Portfolio concentration
            total_portfolio_value = loans_query.aggregate(total=Sum('principal_amount'))['total'] or 0
            
            # Risk distribution
            risk_distribution = {}
            for customer in Customer.objects.all():
                if hasattr(customer, 'risk_profile'):
                    risk_level = customer.risk_profile.risk_level
                    risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1
            
            return {
                'total_loans': total_loans,
                'active_loans': active_loans,
                'defaulted_loans': defaulted_loans,
                'default_rate': round(default_rate, 2),
                'average_loan_amount': float(avg_loan_amount),
                'total_portfolio_value': float(total_portfolio_value),
                'risk_distribution': risk_distribution,
                'portfolio_health_score': self._calculate_portfolio_health_score(default_rate, active_loans, total_loans)
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio health metrics: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_portfolio_health_score(self, default_rate: float, active_loans: int, total_loans: int) -> float:
        """Calculate overall portfolio health score"""
        base_score = 100.0
        
        # Penalize high default rate
        base_score -= default_rate * 2
        
        # Penalize low activity
        activity_rate = (active_loans / total_loans * 100) if total_loans > 0 else 0
        if activity_rate < 50:
            base_score -= (50 - activity_rate) * 0.5
        
        return max(0.0, min(100.0, base_score))


class AnalyticsService:
    """Enhanced Analytics Service with proper expense tracking and profit & loss calculations"""
    
    @staticmethod
    def get_profit_loss_data(start_date=None, end_date=None, branch_id=None):
        """
        Calculate profit & loss using actual expense data instead of estimates
        """
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=365)
        if not end_date:
            end_date = timezone.now().date()
        
        # Base querysets
        loans_query = Loan.objects.filter(
            issue_date__gte=start_date,
            issue_date__lte=end_date
        )
        
        payments_query = Payment.objects.filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date
        )
        
        expenses_query = BusinessExpense.objects.filter(
            expense_date__gte=start_date,
            expense_date__lte=end_date
        )
        
        if branch_id:
            loans_query = loans_query.filter(branch_id=branch_id)
            payments_query = payments_query.filter(loan__branch_id=branch_id)
            expenses_query = expenses_query.filter(branch_id=branch_id)
        
        # Calculate revenue components
        loan_disbursements = loans_query.aggregate(
            total=Sum('principal_amount')
        )['total'] or Decimal('0')
        
        loan_repayments = payments_query.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        # Interest income calculation
        interest_income = Decimal('0')
        for loan in loans_query.filter(scheme__isnull=False):
            if loan.scheme and loan.principal_amount:
                days_active = min(
                    (end_date - loan.issue_date).days,
                    (timezone.now().date() - loan.issue_date).days
                )
                annual_rate = loan.scheme.interest_rate / 100
                interest_income += (loan.principal_amount * annual_rate * days_active) / 365
        
        # Calculate actual expenses by category
        expense_breakdown = {}
        total_expenses = Decimal('0')
        
        expense_categories = ExpenseCategory.objects.all()
        for category in expense_categories:
            category_expenses = expenses_query.filter(category=category).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0')
            
            expense_breakdown[category.name] = {
                'amount': float(category_expenses),
                'percentage': 0.0  # Will calculate after total
            }
            total_expenses += category_expenses
        
        # Calculate percentages
        if total_expenses > 0:
            for category_data in expense_breakdown.values():
                category_data['percentage'] = (category_data['amount'] / float(total_expenses)) * 100
        
        # Calculate profit metrics
        total_revenue = loan_repayments + interest_income
        gross_profit = total_revenue - total_expenses
        profit_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Monthly breakdown for charts
        monthly_data = []
        current_date = start_date
        
        while current_date <= end_date:
            month_start = current_date.replace(day=1)
            if current_date.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1) - timedelta(days=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1) - timedelta(days=1)
            
            month_end = min(month_end, end_date)
            
            # Monthly revenue
            month_payments = payments_query.filter(
                payment_date__gte=month_start,
                payment_date__lte=month_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            # Monthly interest
            month_interest = Decimal('0')
            month_loans = loans_query.filter(
                issue_date__lte=month_end
            ).filter(
                Q(due_date__gte=month_start) | Q(status='active')
            )
            
            for loan in month_loans:
                if loan.scheme and loan.principal_amount:
                    days_in_month = (month_end - max(loan.issue_date, month_start)).days + 1
                    annual_rate = loan.scheme.interest_rate / 100
                    month_interest += (loan.principal_amount * annual_rate * days_in_month) / 365
            
            # Monthly expenses
            month_expenses = expenses_query.filter(
                expense_date__gte=month_start,
                expense_date__lte=month_end
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            month_revenue = month_payments + month_interest
            month_profit = month_revenue - month_expenses
            
            monthly_data.append({
                'month': month_start.strftime('%Y-%m'),
                'revenue': float(month_revenue),
                'expenses': float(month_expenses),
                'profit': float(month_profit),
                'margin': float((month_profit / month_revenue * 100) if month_revenue > 0 else 0)
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return {
            'summary': {
                'total_revenue': float(total_revenue),
                'total_expenses': float(total_expenses),
                'gross_profit': float(gross_profit),
                'profit_margin': float(profit_margin),
                'interest_income': float(interest_income),
                'loan_repayments': float(loan_repayments)
            },
            'expense_breakdown': expense_breakdown,
            'monthly_data': monthly_data,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        }