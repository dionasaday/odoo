# Migration to Odoo 19 & Policy 002/2025 Token-based System

## Overview

This module has been migrated from Odoo 16 to Odoo 19 and refactored to implement **Policy 002/2025: Token-based Lateness System**.

## Key Changes

### 1. Odoo 19 Compatibility
- **Version**: Updated from `16.0.1.0.5` to `19.0.1.0.0`
- **Dependencies**: Verified compatibility with Odoo 19 modules
- **ORM**: All code uses modern Odoo 19 ORM patterns
- **Views**: Updated to Odoo 19 view syntax

### 2. Policy 002/2025: Token-based Lateness System

#### Old System (Bundling)
- Lateness logs were bundled every N occurrences (default: 5)
- One discipline case created per bundle
- Points were positive (accumulated)

#### New System (Token-based)
- **One discipline case per attendance lateness event**
- **Negative points = tokens deducted**
- **No bundling**: Each lateness creates its own case immediately

### 3. Token Deduction Rules

1. **No Notification** → Deduct **3 tokens**
   - Employee is late without notifying manager beforehand
   - Applies regardless of lateness duration

2. **Tier 1 (≤10 min with notification)** → Deduct **1 token**
   - Employee notified manager before scheduled start
   - Lateness is ≤10 minutes beyond grace period

3. **Tier 2 (>10 min with notification)** → Deduct **2 tokens**
   - Employee notified manager before scheduled start
   - Lateness is >10 minutes beyond grace period

### 4. Management Review Threshold

- When an employee has **3+ lateness occurrences** within a period:
  - **No automatic additional punishment**
  - **Activity created** for manager/HR to review
  - Employee flagged for management attention

## Configuration

### Company Settings

Navigate to: **Settings > Companies > [Your Company]**

#### Token Configuration
- **Tier 1 Max Minutes**: Maximum minutes for Tier 1 (default: 10)
- **Tokens for Tier 1**: Tokens deducted for Tier 1 (default: 1)
- **Tokens for Tier 2**: Tokens deducted for Tier 2 (default: 2)
- **Tokens for No Notice**: Tokens deducted without notification (default: 3)

#### Period Configuration
- **Token Period Type**: Weekly or Monthly
- **Weekly Start Day**: Day of week for weekly period (0=Monday, 6=Sunday)
- **Monthly Reset Day**: Day of month for monthly reset (1-31)
- **Management Review Threshold**: Number of occurrences triggering review (default: 3)
- **Starting Tokens per Period**: Tokens allocated at period start (default: 0 = disabled)

## Usage

### Recording Notification

When an employee is late, HR/Manager should:

1. Open the **Lateness Log** for the attendance
2. Check **"Notified Before Start"**
3. Set **"Notification Time"** (when employee notified)
4. Select **"Notification Channel"** (LINE, Phone, Email, etc.)
5. Optionally check **"Manager Confirmed"** if manager verified the notification

### Viewing Lateness

#### From Attendance
- Open any **Attendance** record
- If lateness exists, a **"Lateness"** smart button appears
- Click to view the lateness log

#### From Employee
- Open **Employee** record
- Navigate to discipline-related views to see cases and token deductions

### Management Review

When an employee exceeds the threshold:
- An **activity** is automatically created for the manager
- Manager can review and take appropriate action
- No automatic additional token deduction

## Technical Details

### Models

#### `hr.lateness.log`
New fields:
- `notified_before_start` (Boolean)
- `notified_at` (Datetime)
- `notified_channel` (Selection)
- `manager_confirmed_notification` (Boolean)
- `token_deducted` (Integer)

#### `hr.discipline.case`
New field:
- `attendance_id` (Many2one) - Links case to attendance for idempotency

#### `res.company`
New fields:
- `lateness_tier1_max_minutes`
- `tokens_tier1`, `tokens_tier2`, `tokens_no_notice`
- `token_period_type`, `token_period_start_day`, `token_reset_day_of_month`
- `lateness_repeat_threshold`
- `tokens_starting_per_period`

### Offense Records

New offense records created:
- `offense_late_tier1`: -1 point (1 token)
- `offense_late_tier2`: -2 points (2 tokens)
- `offense_late_no_notice`: -3 points (3 tokens)

### Idempotency

The system ensures:
- **No duplicate cases** for the same attendance
- **No duplicate ledger entries** on recompute
- **Automatic reversal** when attendance check_in is modified

### Processing Flow

1. Attendance created/updated
2. Lateness calculated (check_in vs scheduled start - grace)
3. If lateness > 0:
   - Create/update lateness log
   - Check if case already exists (idempotency)
   - Determine token deduction based on notification and duration
   - Create discipline case with negative points
   - Confirm case (creates ledger entry)
4. Check management review threshold
5. Create activity if threshold exceeded

## Testing Scenarios

### Case 1: Late 7 min with notification → -1 token
1. Employee checks in 7 minutes late (beyond grace)
2. `notified_before_start = True` in lateness log
3. Result: 1 discipline case with -1 point (1 token deducted)

### Case 2: Late 15 min with notification → -2 tokens
1. Employee checks in 15 minutes late (beyond grace)
2. `notified_before_start = True` in lateness log
3. Result: 1 discipline case with -2 points (2 tokens deducted)

### Case 3: Late 5 min without notice → -3 tokens
1. Employee checks in 5 minutes late (beyond grace)
2. `notified_before_start = False` in lateness log
3. Result: 1 discipline case with -3 points (3 tokens deducted)

### Case 4: Three occurrences in period → Management review
1. Employee has 3 lateness occurrences in period
2. Result: Activity created for manager, no additional token deduction

### Case 5: Modify attendance check_in → Previous deduction reversed
1. Attendance check_in time is modified after processing
2. Result: Previous case ledger entry is reversed, new case created with updated lateness

## Migration Notes

### Backward Compatibility
- Legacy fields (`lateness_alert_every_n`, `bundled`) are kept but not used
- Old offense records remain for historical data
- Existing cases are not affected

### Data Migration
- Existing lateness logs retain their data
- Existing cases remain unchanged
- New token-based cases are created going forward

## Support

For issues or questions:
1. Check Odoo logs for errors
2. Verify company configuration
3. Review lateness logs and cases
4. Check ledger entries for token deductions

