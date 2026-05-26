-- SQL script to add vendor bank and UPI details
-- Run this in your MySQL database

ALTER TABLE daybook_vendor 
ADD COLUMN gst_applicable TINYINT(1) NOT NULL DEFAULT 0,
ADD COLUMN bank_name VARCHAR(100) NULL,
ADD COLUMN account_number VARCHAR(50) NULL,
ADD COLUMN ifsc_code VARCHAR(11) NULL,
ADD COLUMN account_holder_name VARCHAR(200) NULL,
ADD COLUMN upi_id VARCHAR(100) NULL;
