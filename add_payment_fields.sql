-- SQL script to add payment mode specific fields to daybook_transaction table
-- Run this in your MySQL database

ALTER TABLE daybook_transaction 
ADD COLUMN bank_name VARCHAR(100) NULL,
ADD COLUMN account_number VARCHAR(50) NULL,
ADD COLUMN upi_id VARCHAR(100) NULL,
ADD COLUMN cheque_number VARCHAR(50) NULL;
