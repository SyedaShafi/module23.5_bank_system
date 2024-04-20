from django import forms
from .models import Transaction
from accounts.models import UserBankAccount
class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            'amount',
            'transaction_type'
        ]

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account') # account value ke pop kore anlam jeta amra amader views a define kore diyechi
        super().__init__(*args, **kwargs)
        self.fields['transaction_type'].disabled = True # ei field disable thakbe
        self.fields['transaction_type'].widget = forms.HiddenInput() # user er theke hide kora thakbe

    def save(self, commit=True):
        self.instance.account = self.account # here self.instance indicates the instance of transaction model, model er instance e form a pathanu hoy always
        self.instance.balance_after_transaction = self.account.balance
        return super().save()




class TransferMoneyForm(TransactionForm):
    account_no = forms.IntegerField()
    class Meta:
        model = Transaction
        fields = [
            'amount',
            'account_no',
            'transaction_type',
        ]


    def clean_account_no(self):
        account_no = self.cleaned_data.get('account_no')
        
        if not UserBankAccount.objects.filter(account_no=account_no).exists():
            raise forms.ValidationError('Account does not exist.')
        
        return account_no
    

    def clean_amount(self): # amount field ke filter korbo
        amount = self.cleaned_data.get('amount') # user er fill up kora form theke amra amount field er value ke niye aslam, 50
        cur_balance = self.account.balance
        if amount > cur_balance:
            raise forms.ValidationError(
                f'You can deposit at most ${cur_balance}'
            )

        return amount












class DepositForm(TransactionForm):
    def clean_amount(self): # amount field ke filter korbo
        min_deposit_amount = 100
        amount = self.cleaned_data.get('amount') # user er fill up kora form theke amra amount field er value ke niye aslam, 50
        if amount < min_deposit_amount:
            raise forms.ValidationError(
                f'You need to deposit at least {min_deposit_amount} $'
            )

        return amount


class WithdrawForm(TransactionForm):

    def clean_amount(self):
        account = self.account
        min_withdraw_amount = 500
        max_withdraw_amount = 20000
        balance = account.balance # 1000
        amount = self.cleaned_data.get('amount')
        if amount < min_withdraw_amount:
            raise forms.ValidationError(
                f'You can withdraw at least {min_withdraw_amount} $'
            )

        if amount > max_withdraw_amount:
            raise forms.ValidationError(
                f'You can withdraw at most {max_withdraw_amount} $'
            )

        if amount > balance: # amount = 5000, tar balance ache 200
            raise forms.ValidationError(
                f'You have {balance} $ in your account. '
                'You can not withdraw more than your account balance'
            )

        return amount



class LoanRequestForm(TransactionForm):
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')

        return amount
    

