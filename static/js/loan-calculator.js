/**
 * Real-time Loan Calculator for Pawnshop Management System
 * Provides instant calculations when users create or modify loans
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const schemeSelect = document.getElementById('id_scheme');
    const principalInput = document.getElementById('id_principal_amount');
    const interestRateInput = document.getElementById('id_interest_rate');
    const processingFeeInput = document.getElementById('id_processing_fee');
    const distributionAmountInput = document.getElementById('id_distribution_amount');
    const issueDateInput = document.getElementById('id_issue_date');
    const dueDateInput = document.getElementById('id_due_date');
    const gracePeriodEndInput = document.getElementById('id_grace_period_end');
    
    // Gold calculation related elements
    const marketPriceInput = document.getElementById('id_market_price_22k');
    const goldKaratSelect = document.getElementById('id_gold_karat');
    const netWeightInput = document.getElementById('id_net_weight');
    
    // Get display containers
    const schemeInfoBox = document.getElementById('scheme-info');
    const loanMetricsBox = document.getElementById('loan-metrics');
    
    // Define karat purity constants
    const KARAT_PURITY = {
        '24': 0.999,
        '22': 0.916,
        '21': 0.875,
        '20': 0.833,
        '18': 0.750,
        '14': 0.583
    };
    
    // Function to format currency
    function formatCurrency(amount) {
        return '₹' + parseFloat(amount).toLocaleString('en-IN', {
            maximumFractionDigits: 2,
            minimumFractionDigits: 2
        });
    }
    
    // Function to calculate loan metrics
    function calculateLoanMetrics() {
        // Get input values
        const principal = parseInt(principalInput.value) || 0;
        const interestRate = parseFloat(interestRateInput.value) || 0;
        const processingFee = parseInt(processingFeeInput.value) || 0;
        
        // Calculate metrics
        const interestAmount = Math.round(principal * interestRate / 100);
        const totalRepayment = principal + interestAmount;
        const distributionAmount = principal - processingFee;
        
        // Calculate monthly interest
        const monthlyInterestRate = interestRate / 12;
        const monthlyInterestAmount = Math.round(principal * monthlyInterestRate / 100);
        const perThousandRate = Math.round((monthlyInterestRate / 100) * 1000);
        
        // Update distribution amount input
        if (distributionAmountInput) {
            distributionAmountInput.value = Math.round(distributionAmount);
        }
        
        // Update loan metrics display
        if (loanMetricsBox) {
            loanMetricsBox.innerHTML = `
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Loan Calculation Summary</h5>
                        <div class="row">
                            <div class="col-md-6">
                                <p><strong>Principal Amount:</strong> ${formatCurrency(principal)}</p>
                                <p><strong>Interest Rate:</strong> ${interestRate}% per annum</p>
                                <p><strong>Processing Fee:</strong> ${formatCurrency(processingFee)}</p>
                            </div>
                            <div class="col-md-6">
                                <p><strong>Interest Amount:</strong> ${formatCurrency(interestAmount)}</p>
                                <p><strong>Total Repayment:</strong> ${formatCurrency(totalRepayment)}</p>
                                <p><strong>Distribution Amount:</strong> ${formatCurrency(distributionAmount)}</p>
                            </div>
                        </div>
                        <div class="row mt-3 bg-light p-2 rounded">
                            <div class="col-12">
                                <h6 class="text-primary"><strong>Monthly Interest Information</strong></h6>
                            </div>
                            <div class="col-md-6">
                                <p><strong>Monthly Rate:</strong> ${monthlyInterestRate.toFixed(2)}%</p>
                            </div>
                            <div class="col-md-6">
                                <p><strong>Monthly Interest:</strong> ${formatCurrency(monthlyInterestAmount)}</p>
                                <p><strong>Rate per ₹1,000:</strong> ${formatCurrency(perThousandRate)}</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
    }
    
    // Function to calculate gold value and display min/max principal amounts
    function calculateGoldValueAndLimits() {
        // Get input values
        const marketPrice = parseFloat(marketPriceInput.value) || 0;
        const goldKarat = goldKaratSelect.value || '22';
        const netWeight = parseFloat(netWeightInput.value) || 0;
        
        // Get purity ratio for the selected karat
        const purityRatio = KARAT_PURITY[goldKarat] || 0.916;  // Default to 22k if not found
        
        // Calculate gold value
        const goldValue = marketPrice * netWeight * purityRatio;
        
        // Update gold value display if element exists
        const goldValueDisplay = document.getElementById('gold-value-display');
        if (goldValueDisplay) {
            goldValueDisplay.textContent = formatCurrency(goldValue);
        }
        
        // Calculate and display min/max loan amounts if elements exist
        const minLoanDisplay = document.getElementById('min-loan-display');
        const maxLoanDisplay = document.getElementById('max-loan-display');
        
        if (minLoanDisplay) {
            const minLoan = goldValue * 0.5;  // 50% of gold value
            minLoanDisplay.textContent = formatCurrency(minLoan);
        }
        
        if (maxLoanDisplay) {
            const maxLoan = goldValue * 0.90;  // 90% of gold value
            maxLoanDisplay.textContent = formatCurrency(maxLoan);
        }
    }
    
    // Function to calculate dates based on scheme duration
    function calculateDates(issueDate, durationDays, graceDays = 30) {
        if (!issueDate) return { dueDate: '', gracePeriodEnd: '' };
        
        // Parse issue date
        const date = new Date(issueDate);
        
        // Calculate due date (issue date + duration days)
        const dueDate = new Date(date);
        dueDate.setDate(date.getDate() + parseInt(durationDays));
        
        // Calculate grace period end (due date + grace days)
        const gracePeriodEnd = new Date(dueDate);
        gracePeriodEnd.setDate(dueDate.getDate() + parseInt(graceDays));
        
        // Format dates as YYYY-MM-DD
        const formatDate = (date) => {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        };
        
        return {
            dueDate: formatDate(dueDate),
            gracePeriodEnd: formatDate(gracePeriodEnd)
        };
    }
    
    // Function to update dates based on scheme loan duration
    function updateDatesFromScheme(scheme) {
        // If issue date is not set, use today's date for calculations
        // This ensures dates are always updated when scheme changes
        let dateToUse = issueDateInput.value;
        
        if (!dateToUse) {
            const today = new Date();
            dateToUse = today.toISOString().split('T')[0];
            
            // Update the issue date input with today's date if it's empty
            if (issueDateInput) {
                issueDateInput.value = dateToUse;
                showNotification('Issue date set to today', 'info');
            }
        }
        
        // Get grace period days from additional_conditions or default to 30
        const gracePeriodDays = 
            (scheme.additional_conditions && scheme.additional_conditions.grace_period_days) || 30;
            
        const { dueDate, gracePeriodEnd } = calculateDates(
            dateToUse, 
            scheme.loan_duration, 
            gracePeriodDays
        );
        
        // Update due date and grace period end inputs
        if (dueDateInput) dueDateInput.value = dueDate;
        if (gracePeriodEndInput) gracePeriodEndInput.value = gracePeriodEnd;
        
        // Show notification about date updates
        if (dueDate && gracePeriodEnd) {
            showNotification(`Due date set to ${dueDate} and grace period to ${gracePeriodEnd}`, 'info');
        }
    }
    
    // Function to show notification if that function exists in the parent scope
    function showNotification(message, type) {
        // Check if notification function exists in parent scope (global)
        if (typeof window.showToast === 'function') {
            window.showToast(message, type || 'info');
        }
    }
    
    // Function to load scheme details
    function loadSchemeDetails() {
        const schemeSelect = document.getElementById('id_scheme');
        const schemeId = schemeSelect.value;
        
        // Clear scheme info if no scheme selected
        if (!schemeId) {
            if (schemeInfoBox) {
                schemeInfoBox.style.display = 'none';
                schemeInfoBox.innerHTML = '';
            }
            
            // Reset help text to default when no scheme is selected
            const schemeHelpText = document.querySelector('#div_id_scheme .form-text');
            if (schemeHelpText) {
                schemeHelpText.innerHTML = 'Select a loan scheme to apply to this loan';
            }
            return;
        }
        
        // Fetch scheme details from API - using the correct URL pattern
        fetch(`/schemes/${schemeId}/json/`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to load scheme details');
                }
                return response.json();
            })
            .then(scheme => {
                // Set scheme info display to visible
                if (schemeInfoBox) {
                    schemeInfoBox.style.display = 'block';
                }
                
                // Get processing fee percentage from additional_conditions or default to 2%
                const processingFeePercentage = 
                    (scheme.additional_conditions && scheme.additional_conditions.processing_fee_percentage) || 1;
                
                // Log the processing fee percentage to help with debugging
                console.log(`Processing fee percentage from scheme: ${processingFeePercentage}%`);
                
                // Update interest rate input with scheme value
                if (interestRateInput) {
                    interestRateInput.value = scheme.interest_rate;
                }
                
                // Calculate processing fee based on principal amount and scheme percentage
                if (processingFeeInput && principalInput.value) {
                    const principal = parseInt(principalInput.value) || 0;
                    processingFeeInput.value = Math.round(principal * processingFeePercentage / 100);
                    console.log(`Calculated processing fee: ${processingFeeInput.value} (${processingFeePercentage}% of ${principal})`);
                }
                
                // Always update dates when scheme changes, regardless of whether issue date is set
                updateDatesFromScheme(scheme);
                
                // Get grace period days from additional_conditions or default to 30
                const gracePeriodDays = 
                    (scheme.additional_conditions && scheme.additional_conditions.grace_period_days) || 30;
                
                // Get no interest period days from additional_conditions or default to 0
                const noInterestPeriodDays = 
                    (scheme.additional_conditions && scheme.additional_conditions.no_interest_period_days) || 0;
                
                // Calculate monthly interest rate
                const monthlyInterestRate = scheme.interest_rate / 12;
                const perThousandRate = (monthlyInterestRate / 100) * 1000;
                
                // Create scheme details HTML with dynamic interest rate structure if available
                let schemeDetailsHTML = `
                    <div class="card-body bg-light">
                        <h5 class="card-title">${scheme.name} Details</h5>
                        <div class="row">
                            <div class="col-md-6">
                                <p><strong>Type:</strong> ${scheme.additional_conditions && scheme.additional_conditions.scheme_type || 'Standard'}</p>
                                <p><strong>Default Interest Rate:</strong> ${scheme.interest_rate}% per annum</p>
                                <p><strong>Monthly Interest:</strong> ${monthlyInterestRate.toFixed(2)}% per month</p>
                                <p><strong>Per ₹1,000 Rate:</strong> ₹${perThousandRate.toFixed(2)}</p>
                            </div>
                            <div class="col-md-6">
                                <p><strong>Loan Period:</strong> ${scheme.loan_duration} days</p>
                                <p><strong>No Interest Period:</strong> ${noInterestPeriodDays} days</p>
                                <p><strong>Grace Period:</strong> ${gracePeriodDays} days</p>
                            </div>
                        </div>
                `;
                
                // Add dynamic interest rate structure if available
                if (scheme.interest_rate_structure && Object.keys(scheme.interest_rate_structure).length > 0) {
                    schemeDetailsHTML += `
                        <div class="mt-3">
                            <h6 class="font-weight-bold">Dynamic Interest Rate Structure</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-bordered">
                                    <thead class="thead-light">
                                        <tr>
                                            <th>Loan Tenure</th>
                                            <th>Interest Rate</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                    `;
                    
                    // Add each interest rate range
                    for (const [range, rate] of Object.entries(scheme.interest_rate_structure)) {
                        let rangeDisplay = range;
                        if (range.includes('-')) {
                            rangeDisplay = `${range} months`;
                        } else if (range.endsWith('+')) {
                            rangeDisplay = `> ${range.replace('+', '')} months`;
                        } else {
                            rangeDisplay = `${range} month${range !== '1' ? 's' : ''}`;
                        }
                        
                        schemeDetailsHTML += `
                            <tr>
                                <td>${rangeDisplay}</td>
                                <td>${rate}%</td>
                            </tr>
                        `;
                    }
                    
                    schemeDetailsHTML += `
                                    </tbody>
                                </table>
                            </div>
                            <p class="small text-muted mb-0">Interest rate is determined based on loan tenure in months</p>
                        </div>
                    `;
                }
                
                schemeDetailsHTML += `</div>`;
                        
                // Display scheme details in the info box
                if (schemeInfoBox) {
                    schemeInfoBox.innerHTML = schemeDetailsHTML;
                }
                
                // Update the help text with scheme details
                const schemeHelpText = document.querySelector('#div_id_scheme .form-text');
                if (schemeHelpText) {
                    let helpTextHTML = `
                        <strong>${scheme.name}:</strong> ${scheme.interest_rate}% base interest | 
                        ${scheme.loan_duration} days term
                    `;
                    
                    // Add dynamic interest note if available
                    if (scheme.interest_rate_structure && Object.keys(scheme.interest_rate_structure).length > 0) {
                        helpTextHTML += ` | <span class="text-success">Dynamic interest rates based on tenure</span>`;
                    }
                    
                    schemeHelpText.innerHTML = helpTextHTML;
                }
                
                // Calculate loan metrics with updated values
                calculateLoanMetrics();
            })
            .catch(error => {
                console.error('Error loading scheme details:', error);
                showNotification('Failed to load scheme details: ' + error.message, 'error');
            });
    }
    
    // Set up event listeners
    if (schemeSelect) {
        // Adding a separate event listener for the scheme select to ensure dates always update
        schemeSelect.addEventListener('change', function() {
            // Load scheme details will update dates
            loadSchemeDetails();
        });
    }
    
    if (principalInput) {
        principalInput.addEventListener('input', function() {
            // If a scheme is selected, recalculate processing fee based on scheme percentage
            if (schemeSelect && schemeSelect.value && processingFeeInput) {
                // Re-fetch scheme details to get processing fee percentage
                loadSchemeDetails();
            } else {
                // Otherwise just calculate loan metrics with current values
                calculateLoanMetrics();
            }
        });
    }
    
    // Add event listeners for gold value calculation
    if (marketPriceInput) {
        marketPriceInput.addEventListener('input', calculateGoldValueAndLimits);
    }
    
    if (goldKaratSelect) {
        goldKaratSelect.addEventListener('change', calculateGoldValueAndLimits);
    }
    
    if (netWeightInput) {
        netWeightInput.addEventListener('input', calculateGoldValueAndLimits);
    }
    
    if (interestRateInput) {
        interestRateInput.addEventListener('input', calculateLoanMetrics);
    }
    
    if (processingFeeInput) {
        processingFeeInput.addEventListener('input', calculateLoanMetrics);
    }
    
    if (issueDateInput) {
        issueDateInput.addEventListener('change', function() {
            // If a scheme is selected, update maturity date
            if (schemeSelect && schemeSelect.value) {
                loadSchemeDetails();
            }
        });
    }
    
    // Initial calculation if values are pre-populated
    if (schemeSelect && schemeSelect.value) {
        loadSchemeDetails();
    } else {
        calculateLoanMetrics();
    }
    
    // Calculate gold value if all required fields have values
    if (marketPriceInput && marketPriceInput.value && 
        goldKaratSelect && goldKaratSelect.value && 
        netWeightInput && netWeightInput.value) {
        calculateGoldValueAndLimits();
    }
});