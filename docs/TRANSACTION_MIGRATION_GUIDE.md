# Migration Guide: Transaction-Based Repository

## Overview

This guide explains how to migrate from the old `BookingRepository` to the new `BookingRepositoryV2` with:
- **ACID transactions** to prevent race conditions
- **Input validation** with Pydantic
- **Comprehensive error handling** with retry logic
- **Structured logging** and monitoring

## What Changed?

### 1. Input Validation with Pydantic

**Before:**
```python
# No validation - accepts anything
await BookingRepository.create_booking(user_id, username, date, time, service_id)
```

**After:**
```python
# Automatic validation with Pydantic
success, error = await BookingRepositoryV2.create_booking_atomic(
    user_id=123,
    username="john_doe",
    date_str="2026-02-15",
    time_str="14:00",
    service_id=1,
    duration_minutes=60
)

if not success:
    print(f"Failed: {error}")  # User-friendly error message
```

### 2. Atomic Transactions

**Before (Race Condition Risk):**
```python
# Check and insert - NOT ATOMIC!
is_free = await BookingRepository.is_slot_free(date, time)
if is_free:
    # Another user might book here! ⚠️
    await BookingRepository.create_booking(...)
```

**After (ACID Transaction):**
```python
# Check + insert in single transaction - ATOMIC ✅
success, error = await BookingRepositoryV2.create_booking_atomic(
    user_id=123,
    username="john",
    date_str="2026-02-15",
    time_str="14:00"
)
# Race conditions impossible - database lock prevents conflicts
```

### 3. Error Handling

**Before:**
```python
try:
    await BookingRepository.create_booking(...)
except Exception as e:
    # What type of error? Can we retry?
    print(f"Error: {e}")
```

**After:**
```python
from utils.error_handler import async_retry_on_error, safe_operation

# Automatic retries for transient errors
@async_retry_on_error(max_attempts=3, delay=1.0)
async def my_booking_flow():
    async with safe_operation("book_slot", user_id=123):
        success, error = await BookingRepositoryV2.create_booking_atomic(...)
        return success
```

## Migration Steps

### Step 1: Install Pydantic

```bash
pip install pydantic==2.6.1
```

### Step 2: Update Imports

**In your handlers (e.g., `booking_handlers.py`):**

```python
# OLD
from database.repositories.booking_repository import BookingRepository

# NEW
from database.repositories.booking_repository_v2 import BookingRepositoryV2
from utils.error_handler import handle_telegram_error, safe_operation
from validation.schemas import BookingCreateInput
```

### Step 3: Replace Method Calls

#### Creating Bookings

**OLD:**
```python
try:
    success = await BookingRepository.create_booking(
        user_id, username, date_str, time_str, service_id
    )
    if success:
        await message.answer("✅ Booking created!")
    else:
        await message.answer("❌ Slot is taken")
except Exception as e:
    await message.answer("❌ Error occurred")
```

**NEW:**
```python
try:
    success, error = await BookingRepositoryV2.create_booking_atomic(
        user_id=user_id,
        username=username,
        date_str=date_str,
        time_str=time_str,
        service_id=service_id,
        duration_minutes=60
    )
    
    if success:
        await message.answer("✅ Booking created successfully!")
    else:
        await message.answer(f"❌ {error}")
        
except ValidationError as e:
    await message.answer(f"❌ Invalid input: {e}")
except DatabaseError as e:
    logger.error(f"Database error: {e}")
    await message.answer("❌ System error. Please try again later.")
```

#### Canceling Bookings

**OLD:**
```python
success = await BookingRepository.delete_booking(booking_id, user_id)
```

**NEW:**
```python
success, error = await BookingRepositoryV2.cancel_booking_atomic(
    booking_id=booking_id,
    user_id=user_id,
    reason="User requested cancellation"
)

if not success:
    await message.answer(f"❌ {error}")
```

#### Blocking Slots

**OLD:**
```python
success, cancelled = await BookingRepository.block_slot_with_notification(
    date_str, time_str, admin_id, reason
)
```

**NEW:**
```python
success, cancelled_users, error = await BookingRepositoryV2.block_slot_atomic(
    date_str=date_str,
    time_str=time_str,
    admin_id=admin_id,
    reason=reason
)

if success:
    # Notify cancelled users
    for user in cancelled_users:
        await bot.send_message(user['user_id'], f"Your booking was cancelled: {reason}")
else:
    await callback.answer(f"Failed: {error}", show_alert=True)
```

### Step 4: Add Validation to Handlers

**Example: Validate user input before processing:**

```python
from validation.schemas import TimeSlotInput, validate_date_string, validate_time_string
from pydantic import ValidationError

@router.message(BookingStates.awaiting_time)
async def process_time_selection(message: Message, state: FSMContext):
    try:
        # Validate time input
        time_str = message.text.strip()
        time = validate_time_string(time_str)  # Raises ValidationError if invalid
        
        data = await state.get_data()
        date_str = data['date']
        
        # Validate complete slot
        slot = TimeSlotInput(
            date=validate_date_string(date_str),
            time=time
        )
        
        # Proceed with booking...
        success, error = await BookingRepositoryV2.create_booking_atomic(...)
        
    except ValidationError as e:
        await message.answer(f"❌ Invalid time: {e}")
        return
```

## Benefits

### 1. Race Condition Prevention

✅ **Atomic operations** with `BEGIN IMMEDIATE` transactions  
✅ **No more double-bookings** even under high load  
✅ **Consistent state** - all-or-nothing guarantees  

### 2. Better Error Messages

```python
# User gets clear, actionable messages:
"Booking limit reached (3)"
"Slot was just taken by another user"
"Can only cancel 24h before booking"
"Time must be on the hour (e.g., 10:00, 14:00)"
```

### 3. Automatic Retries

```python
# Transient errors (network issues, DB locks) are retried automatically
@async_retry_on_error(max_attempts=3, delay=1.0, backoff=2.0)
async def my_function():
    # This will retry up to 3 times with exponential backoff
    pass
```

### 4. Monitoring & Debugging

```python
# Structured logging for better debugging
async with safe_operation("create_booking", user_id=123, slot="2026-02-15 14:00"):
    # All errors are logged with context
    # High severity errors sent to Sentry automatically
    pass
```

## Testing

### Unit Tests

```python
import pytest
from database.repositories.booking_repository_v2 import BookingRepositoryV2
from validation.schemas import ValidationError

@pytest.mark.asyncio
async def test_create_booking_validates_input():
    # Invalid user_id should fail
    with pytest.raises(ValidationError):
        await BookingRepositoryV2.create_booking_atomic(
            user_id=-1,  # Invalid!
            username="test",
            date_str="2026-02-15",
            time_str="14:00"
        )

@pytest.mark.asyncio
async def test_create_booking_prevents_race_condition():
    # Create 100 concurrent bookings for same slot
    tasks = [
        BookingRepositoryV2.create_booking_atomic(
            user_id=i,
            username=f"user{i}",
            date_str="2026-02-15",
            time_str="14:00"
        )
        for i in range(100)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Only ONE should succeed
    successes = sum(1 for success, _ in results if success)
    assert successes == 1
```

## Rollback Plan

If issues arise, you can rollback:

1. Keep `booking_repository.py` unchanged
2. Use `BookingRepositoryV2` only in new code
3. Gradually migrate handlers one by one
4. Both repositories can coexist

## Performance Considerations

### Transaction Overhead

- **`BEGIN IMMEDIATE`** locks database briefly (~1-5ms)
- **Acceptable** for booking systems (not high-frequency trading)
- **Alternative**: Use PostgreSQL with row-level locking for higher concurrency

### Retry Impact

- Retries add latency (1s + 2s + 4s = 7s max)
- Only for **transient errors** (rare in production)
- Configure retry params per operation:

```python
# Fast operations - fewer retries
@async_retry_on_error(max_attempts=2, delay=0.5)

# Critical operations - more retries
@async_retry_on_error(max_attempts=5, delay=1.0, backoff=2.0)
```

## Next Steps

1. ✅ Install Pydantic: `pip install pydantic==2.6.1`
2. ✅ Update one handler as proof-of-concept
3. ✅ Test thoroughly in staging
4. ✅ Monitor error rates with Sentry
5. ✅ Gradually migrate all handlers
6. ✅ Deprecate old `BookingRepository`

## Questions?

Check these files:
- `validation/schemas.py` - All Pydantic schemas
- `utils/error_handler.py` - Error handling utilities
- `database/repositories/booking_repository_v2.py` - New repository
- `docs/API.md` - Complete API reference

---

**Summary**: The new transaction-based repository eliminates race conditions, provides better error handling, and validates all inputs automatically. Migration is gradual and safe.
