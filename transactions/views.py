from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.http import HttpResponse
from django.views.generic import CreateView, ListView
from transactions.constants import DEPOSIT, WITHDRAWAL,LOAN, LOAN_PAID, TRANSFORMED, RECEIVED
from datetime import datetime
from django.db.models import Sum

from transactions.forms import (
    DepositForm,
    WithdrawForm,
    LoanRequestForm,
    TransferMoneyForm,
)

from transactions.models import Transaction
from accounts.models import UserBankAccount
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string


def send_transaction_email(user, amount, subject, template):
        message = render_to_string(template, {
            'user' : user,
            'amount' : amount,
        })
        send_email = EmailMultiAlternatives(subject, '', to=[user.email])
        send_email.attach_alternative(message, "text/html")
        send_email.send()


class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = 'transactions/transaction_form.html'
    model = Transaction
    title = ''
    success_url = reverse_lazy('transaction_report')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'account': self.request.user.account
        })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs) # template e context data pass kora
        context.update({
            'title': self.title
        })

        return context





class MoneyTransfer(TransactionCreateMixin):
    form_class = TransferMoneyForm
    title = 'Transfer Money'
    success_url = reverse_lazy('transaction_report')

    def get_initial(self):
        initial = {'transaction_type': TRANSFORMED}
        return initial

    def form_valid(self, form): # self: instance of DepositMoneyView and form: instance of DepositForm
        amount = form.cleaned_data.get('amount')
        account_no = form.cleaned_data.get('account_no')
        cur_account = self.request.user.account # we can access the data of current logged in user by using self.request.user from anywhere in the views file

        account = UserBankAccount.objects.get(account_no=account_no)

        if amount<=cur_account.balance:
            cur_account.balance -= amount # amount = 200, tar ager balance = 0 taka new balance = 0+200 = 200
            account.balance += amount
            transaction_type_receiver = RECEIVED

            Transaction.objects.create(account=account, amount=amount, balance_after_transaction=account.balance,
            transaction_type=transaction_type_receiver)

            cur_account.save(update_fields=['balance'])
            account.save(update_fields=['balance'])


        messages.success(
            self.request,
            f'{"{:,.2f}".format(float(amount))}$ was transfered from {cur_account.user} account successfully'
        )
        send_transaction_email(self.request.user, amount, "Money Transfer Message", "transactions/money_transfer_mail.html")
        send_transaction_email(account.user, amount, "Money Received Message", "transactions/money_received_mail.html")

        return super().form_valid(form)




class DepositMoneyView(TransactionCreateMixin):
    form_class = DepositForm
    title = 'Deposit'

    def get_initial(self):
        initial = {'transaction_type': DEPOSIT}
        return initial

    def form_valid(self, form): # self: instance of DepositMoneyView and form: instance of DepositForm
        amount = form.cleaned_data.get('amount')
        account = self.request.user.account # we can access the data of current logged in user by using self.request.user from anywhere in the views file

        account.balance += amount # amount = 200, tar ager balance = 0 taka new balance = 0+200 = 200
        account.save(
            update_fields=[
                'balance'
            ]
        )

        messages.success(
            self.request,
            f'{"{:,.2f}".format(float(amount))}$ was deposited to your account successfully'
        )

        # sending mail
        send_transaction_email(self.request.user, amount, "Deposite Message", "transactions/deposite_mail.html")

        return super().form_valid(form)





class WithdrawMoneyView(TransactionCreateMixin):
    form_class = WithdrawForm
    title = 'Withdraw Money'

    def get_initial(self):
        initial = {'transaction_type': WITHDRAWAL}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')

        if amount == self.request.user.account.balance and self.request.user.account.is_bankrupt :
            messages.warning(
            self.request,
            f'Bank is bankrupt')
            return redirect('withdraw_money')

        self.request.user.account.balance -= form.cleaned_data.get('amount')
        # balance = 300
        # amount = 5000
        self.request.user.account.save(update_fields=['balance'])

        messages.success(
            self.request,
            f'Successfully withdrawn {"{:,.2f}".format(float(amount))}$ from your account'
        )

        send_transaction_email(self.request.user, amount, "Withdrawal Message", "transactions/withdrawal_email.html")

        return super().form_valid(form)

class LoanRequestView(TransactionCreateMixin):
    form_class = LoanRequestForm
    title = 'Request For Loan'

    def get_initial(self):
        initial = {'transaction_type': LOAN}
        return initial

    def form_valid(self, form):
        amount = form.cleaned_data.get('amount')
        current_loan_count = Transaction.objects.filter(
            account=self.request.user.account, transaction_type=3, loan_approve=True).count()
        
        if current_loan_count >= 3:
            return HttpResponse("You have cross the loan limits")
        messages.success(
            self.request,
            f'Loan request for {"{:,.2f}".format(float(amount))}$ submitted successfully'
        )
        
        send_transaction_email(self.request.user, amount, "Loan Request", "transactions/loan_request_email.html")

        return super().form_valid(form)
    



class TransactionReportView(LoginRequiredMixin, ListView):
    template_name = 'transactions/transaction_report.html'
    model = Transaction
    balance = 0 # filter korar pore ba age amar total balance ke show korbe
    

    def get_queryset(self):

        queryset = super().get_queryset().filter(
            account=self.request.user.account
        )

        start_date_str = self.request.GET.get('start_date')
        end_date_str = self.request.GET.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            queryset = queryset.filter(timestamp__date__gte=start_date, timestamp__date__lte=end_date)

            # Calculate balance within the date range
            self.balance = Transaction.objects.filter(
                timestamp__date__gte=start_date, timestamp__date__lte=end_date
            ).aggregate(Sum('amount'))['amount__sum']

        else:
            # it sets the balance to the current balance of the user's account:
            self.balance = self.request.user.account.balance
       
        return queryset.distinct() # unique queryset hote hobe
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'account': self.request.user.account
        })

        return context
    
        

        
class PayLoanView(LoginRequiredMixin, View):
    def get(self, request, loan_id):
        loan = get_object_or_404(Transaction, id=loan_id)
        print(loan)
        if loan.loan_approve:
            user_account = loan.account
                # Reduce the loan amount from the user's balance
                # 5000, 500 + 5000 = 5500
                # balance = 3000, loan = 5000
            if loan.amount < user_account.balance:
                user_account.balance -= loan.amount
                loan.balance_after_transaction = user_account.balance
                user_account.save()
                loan.loan_approve = True
                loan.transaction_type = LOAN_PAID
                loan.save()
                return redirect('loan_list')
            else:
                messages.error(
            self.request,
            f'Loan amount is greater than available balance'
        )

        return redirect('loan_list')


class LoanListView(LoginRequiredMixin,ListView):
    model = Transaction
    template_name = 'transactions/loan_request.html'
    context_object_name = 'loans' # loan list ta ei loans context er moddhe thakbe
    
    def get_queryset(self):
        user_account = self.request.user.account
        queryset = Transaction.objects.filter(account=user_account, transaction_type=LOAN)
        print(queryset)
        return queryset
    


