from __future__ import annotations

DEFAULT_TEXT_TEMPLATES: dict[str, str] = {
    "welcome_text": (
        "Welcome to Coin Shop Bot.\n"
        "Use the menu buttons below.\n"
        "Important: All deposits require manual admin approval."
    ),
    "load_coins_text": "Select a coin package:",
    "shop_select_game_text": "Select game:",
    "no_active_items_text": "No active items available right now.",
    "bank_receipt_request_text": (
        "Bank transfer selected.\n"
        "1) Send payment to this account\n"
        "2) Upload receipt screenshot/photo\n"
        "3) Wait for admin approval"
    ),
    "trx_payment_text": (
        "TRX payment created.\n"
        "Send exact amount to wallet below.\n"
        "Payment detection is automatic, but coin loading is always manual admin approval."
    ),
    "cancel_text": "Cancelled. Back to main menu.",
    "use_menu_buttons_text": "Please use the menu buttons.",
    "balance_text": "Your balance: {balance} COIN",
    "no_active_orders_text": "No active orders.",
    "history_header_text": "History (latest):",
    "no_bank_deposit_records_text": "- no bank deposit records",
    "no_crypto_deposit_records_text": "- no crypto deposit records",
    "no_order_records_text": "- no order records",
    "main_menu_below_text": "Main menu is below.",
    "choose_action_text": "Choose an action:",
    "package_not_available_text": "Package not available.",
    "choose_payment_method_text": "Choose payment method:",
    "package_not_found_text": "Package not found.",
    "upload_receipt_prompt_text": "Now upload your receipt as photo/document.",
    "no_products_for_game_text": "No products for this game.",
    "select_product_text": "Select product:",
    "session_expired_select_game_text": "Session expired. Please select game again.",
    "product_not_found_text": "Product not found.",
    "user_not_found_text": "User not found.",
    "purchase_failed_text": "Purchase failed: {error}",
    "purchase_success_text": (
        "Purchase success. {price} COIN deducted.\n"
        "New balance: {balance} COIN\n\n"
        "Now send your {id_label}:"
    ),
    "no_package_selected_text": "No package selected. Please start again.",
    "upload_receipt_only_text": "Please upload photo or document receipt.",
    "deposit_received_text": "Receipt received. Request ID: #{request_id}.\n{waiting_text}",
    "invalid_game_user_id_text": "Please enter a valid game user ID.",
    "ask_iban_text": "Now send your IBAN:",
    "invalid_iban_text": "Please enter a valid IBAN.",
    "ask_full_name_text": "Now send Name Surname:",
    "invalid_full_name_text": "Please enter full name and surname.",
    "ask_bank_name_text": "Now send Bank Name:",
    "invalid_bank_name_text": "Please enter bank name.",
    "order_session_expired_text": "Order session expired. Please buy again.",
    "order_submitted_text": "Order #{order_id} is submitted for admin processing.\n{order_received_text}",
    "deposit_waiting": "Your deposit request has been received. Please wait for admin approval.",
    "order_received": "Your order is created. Our admin will complete delivery soon.",
}

TEMPLATE_LABELS: dict[str, str] = {
    "welcome_text": "Welcome Message",
    "load_coins_text": "Load Coins Header",
    "shop_select_game_text": "Shop Select Game",
    "no_active_items_text": "No Active Items",
    "bank_receipt_request_text": "Bank Receipt Instructions",
    "trx_payment_text": "TRX Payment Intro",
    "balance_text": "Balance Message",
    "deposit_waiting": "Deposit Waiting Notice",
    "order_received": "Order Received Notice",
    "purchase_success_text": "Purchase Success Message",
    "order_submitted_text": "Order Submitted Message",
}

WELCOME = DEFAULT_TEXT_TEMPLATES["welcome_text"]
LOAD_COINS = DEFAULT_TEXT_TEMPLATES["load_coins_text"]
SHOP_SELECT_GAME = DEFAULT_TEXT_TEMPLATES["shop_select_game_text"]
NO_ACTIVE_ITEMS = DEFAULT_TEXT_TEMPLATES["no_active_items_text"]
BANK_RECEIPT_REQUEST = DEFAULT_TEXT_TEMPLATES["bank_receipt_request_text"]
TRX_PAYMENT_TEXT = DEFAULT_TEXT_TEMPLATES["trx_payment_text"]
