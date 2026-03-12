-- SQL Script to add missing fields to daybook_transaction table
-- Run this in MySQL if Django migrations don't work

-- Add IFSC Code field
ALTER TABLE daybook_transaction 
ADD COLUMN ifsc_code VARCHAR(11) NULL AFTER account_number;

-- Add Account Holder Name field
ALTER TABLE daybook_transaction 
ADD COLUMN account_holder_name VARCHAR(200) NULL AFTER ifsc_code;

-- Verify the changes
DESCRIBE daybook_transaction;
