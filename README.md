# DentalPracticeChatbot

```
Workflow: 
Register a new patient.
Find available appointment slots.
Book an appointment without double-booking.
Verify an existing patient.
Reschedule or cancel an appointment.
Escalate dental emergencies to staff.
```

```
Data Schemes:
patients
- id
- full_name
- phone
- date_of_birth
- insurance_name

availability
- id
- start_time
- end_time
- appointment_type
- is_available

appointments
- id
- patient_id
- slot_id
- appointment_type
- status
- emergency_summary
```

```
Execution plan
Scaffold the project and commit it.
Create SQL tables and seed realistic patients and time slots.
Implement scheduling functions with conflict validation.
Connect the LLM through tool/function calling.
Build the chat interface.
Test the required scenarios and failure cases.
Write the README and record the demo.
```