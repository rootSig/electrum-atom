import re
import platform
from decimal import Decimal

from PyQt4.QtGui import *
from PyQt4.QtCore import *
import PyQt4.QtCore as QtCore
import PyQt4.QtGui as QtGui

from electrum_gui.qrcodewidget import QRCodeWidget
from electrum_gui import bmp, pyqrnative, qrscanner

from electrum_gui.i18n import _


if platform.system() == 'Windows':
    MONOSPACE_FONT = 'Lucida Console'
elif platform.system() == 'Darwin':
    MONOSPACE_FONT = 'Monaco'
else:
    MONOSPACE_FONT = 'monospace'


class QR_Window(QWidget):

    def __init__(self, exchanger):
        QWidget.__init__(self)
        self.exchanger = exchanger
        self.setWindowTitle('Electrum - '+_('Invoice'))
        self.setMinimumSize(800, 250)
        self.address = ''
        self.labe = ''
        self.amount = 0
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        main_box = QHBoxLayout()
        
        self.qrw = QRCodeWidget()
        main_box.addWidget(self.qrw, 1)

        vbox = QVBoxLayout()
        main_box.addLayout(vbox)

        self.address_label = QLabel("")
        #self.address_label.setFont(QFont(MONOSPACE_FONT))
        vbox.addWidget(self.address_label)

        self.label_label = QLabel("")
        vbox.addWidget(self.label_label)

        self.amount_label = QLabel("")
        vbox.addWidget(self.amount_label)

        vbox.addStretch(1)
        self.setLayout(main_box)


    def set_content(self, addr, label, amount, currency):
        self.address = addr
        address_text = "<span style='font-size: 18pt'>%s</span>" % addr if addr else ""
        self.address_label.setText(address_text)

        if currency == 'BTC': currency = None
        amount_text = ''
        if amount:
            if currency:
                self.amount = Decimal(amount) / self.exchanger.exchange(1, currency) if currency else amount
            else:
                self.amount = Decimal(amount)
            self.amount = self.amount.quantize(Decimal('1.0000'))

            if currency:
                amount_text += "<span style='font-size: 18pt'>%s %s</span><br/>" % (amount, currency)
            amount_text += "<span style='font-size: 21pt'>%s</span> <span style='font-size: 16pt'>BTC</span> " % str(self.amount) 
        self.amount_label.setText(amount_text)

        self.label = label
        label_text = "<span style='font-size: 21pt'>%s</span>" % label if label else ""
        self.label_label.setText(label_text)

        msg = 'bitcoin:'+self.address
        if self.amount is not None:
            msg += '?amount=%s'%(str( self.amount))
            if self.label is not None:
                msg += '&label=%s'%(self.label)
        elif self.label is not None:
            msg += '?label=%s'%(self.label)
            
        self.qrw.set_addr( msg )

            




def get_info():
    return 'Point of Sale', _('Show QR code window and amounts requested for each address. Add menu item to request amount.')

def init(wallet):
    wallet.requested_amounts = wallet.config.get('requested_amounts',{}) 


def init_gui(gui):
    gui.qr_window = None



enabled = False

def is_enabled():
    return False

def toggle(gui):
    global enabled
    enabled = not enabled
    toggle_QR_window(gui, enabled)

    if enabled:
        gui.wallet.set_hook('item_changed', item_changed)
        gui.wallet.set_hook('current_item_changed', recv_changed)
        gui.wallet.set_hook('receive_menu', receive_menu)
        gui.wallet.set_hook('update_receive_item', update_receive_item)
        gui.wallet.set_hook('timer_actions', timer_actions)
        gui.wallet.set_hook('close_main_window', close_main_window)
    else:
        gui.wallet.unset_hook('item_changed', item_changed)
        gui.wallet.unset_hook('current_item_changed', recv_changed)
        gui.wallet.unset_hook('receive_menu', receive_menu)
        gui.wallet.unset_hook('update_receive_item', update_receive_item)
        gui.wallet.unset_hook('timer_actions', timer_actions)
        gui.wallet.unset_hook('close_main_window', close_main_window)
        

    return enabled


def toggle_QR_window(self, show):
    if show and not self.qr_window:
        self.qr_window = QR_Window(self.exchanger)
        self.qr_window.setVisible(True)
        self.qr_window_geometry = self.qr_window.geometry()
        item = self.receive_list.currentItem()
        if item:
            address = str(item.text(1))
            label = self.wallet.labels.get(address)
            amount, currency = self.wallet.requested_amounts.get(address, (None, None))
            self.qr_window.set_content( address, label, amount, currency )

    elif show and self.qr_window and not self.qr_window.isVisible():
        self.qr_window.setVisible(True)
        self.qr_window.setGeometry(self.qr_window_geometry)

    elif not show and self.qr_window and self.qr_window.isVisible():
        self.qr_window_geometry = self.qr_window.geometry()
        self.qr_window.setVisible(False)

    #self.print_button.setHidden(self.qr_window is None or not self.qr_window.isVisible())
    self.receive_list.setColumnHidden(2, self.qr_window is None or not self.qr_window.isVisible())
    #self.receive_list.setColumnWidth(1, 200)



def item_changed(self, item, column):
    if column == 4:
        address = str( item.text(0) )
        text = str( item.text(column) )
        try:
            seq = self.wallet.get_address_index(address)
            index = seq[-1]
        except:
            print "cannot get index"
            return

        text = text.strip().upper()
        print text
        m = re.match('^(\d+(|\.\d*))\s*(|BTC|EUR|USD|GBP|CNY|JPY|RUB|BRL)$', text)
        if m:
            amount = m.group(1)
            currency = m.group(3)
            if not currency:
                currency = 'BTC'
            else:
                currency = currency.upper()
                    
            self.wallet.requested_amounts[address] = (amount, currency)
            self.wallet.config.set_key('requested_amounts', self.wallet.requested_amounts, True)

            label = self.wallet.labels.get(address)
            if label is None:
                label = self.merchant_name + ' - %04d'%(index+1)
                self.wallet.labels[address] = label

            if self.qr_window:
                self.qr_window.set_content( address, label, amount, currency )

        else:
            item.setText(column,'')
            if address in self.wallet.requested_amounts:
                self.wallet.requested_amounts.pop(address)
            
        self.update_receive_item(self.receive_list.currentItem())


def recv_changed(self, a):
    if a is not None and self.qr_window and self.qr_window.isVisible():
        address = str(a.text(0))
        label = self.wallet.labels.get(address)
        try:
            amount, currency = self.wallet.requested_amounts.get(address, (None, None))
        except:
            amount, currency = None, None
        self.qr_window.set_content( address, label, amount, currency )



def edit_amount(self):
    l = self.receive_list
    item = l.currentItem()
    item.setFlags(Qt.ItemIsEditable|Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)
    l.editItem( item, 4 )
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)

def receive_menu(self, menu):
    menu.addAction(_("Request amount"), lambda: edit_amount(self))


def update_receive_item(self, address, item):
    try:
        amount, currency = self.wallet.requested_amounts.get(address, (None, None))
    except:
        print "cannot get requested amount", address, self.wallet.requested_amounts.get(address)
        amount, currency = None, None
            
    amount_str = amount + (' ' + currency if currency else '') if amount is not None  else ''
    item.setData(4,0,amount_str)


def close_main_window(self):
    if self.qr_window: 
        self.qr_window.close()
        self.qr_window = None


def timer_actions(self):
    if self.qr_window:
        self.qr_window.qrw.update_qr()
