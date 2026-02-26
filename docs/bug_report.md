# Bug Report: Pivot Point Orthopedics AI Agent

## Summary

Bugs identified across 12 test calls to the Pivot Point Orthopedics AI receptionist.

### Bug 1: Date of Birth in Creating Patient Profile

- **Severity:** Low - Medium
- **Call:** transcripts/new_appointment_20260224_050243.txt
- **Timestamp:** 0:43
- **Description:** Agent assigns date of birth to patient profile without asking first
- **Expected behavior:** Agent should ask the patient for a date of birth before assigning one to them.

### Bug 2: Patient Record

- **Severity:** High
- **Call:** transcripts/reschedule_20260224_051725.txt
- **Timestamp:** 1:05, then 1:49
- **Description:** Agent could not find the profile of an existing patient and then redirected them to the "clinic support team" to help with their needs:
-   ***1:05 Incident:*** "Let me confirm your name is Mike Chen and your date of birth is June 22nd 1980 is that correct? If so, could you please spell your first and last name for me?" ; "Yes, that’s correct. My first name is spelled M-I-K-E, and my last name is C-H-E-N." ; "Would you like me to look up your record using your phone number? If so, please provide the number you have on file with us. If you're not sure, just let me know and we can confirm your name and date of birth again."
-   **Expected Behavior:** Agent should let patient know that they can't find their record before trying other methods because patient could have misremembered details, called the wrong clinic, or gave wrong information.
-   ***1:49 Incident:***  "Let me confirm I have your phone number as 5550198 and your date of birth is June 22nd, 1980. Is that correct?" ; "Yes." ; "I can't pull up your record right now, so I can't help with rescheduling at the moment. I'll make sure our clinic support team follows up with you. Please hold while I document this for them."
- **Expected behavior:** Agent should redirect their call to someone who can help the patient while on the phone rather than just saying that their team will call them later.
- **Note:** This bug occurs in many other calls if the patient profile isn't created on the phone

### Bug 3: Unique Case of Transferring the Call

- **Severity:** Medium
- **Call:** transcripts/sunday_appointment_20260224_054527.txt
- **Timestamp:** 2:24
- **Description:** Agent actually "transferred" the call instead of saying they will refer to the clinic support team, which is a different scenario to how the Agent handled other cases with similar issues.

### Bug 4: Spanish Speaker

- **Severity:** High
- **Call:** transcripts/topic_switch_20260224_061617.txt
- **Timestamp:** Entire Call
- **Description:** Agent can't understand a Spanish speaker and keeps asking "How may I help you today?" or similar phrases.
- **Excerpt:**
[AGENT]: How may I help you today?

[PATIENT]: Quiero agendar una cita de seguimiento para el tobillo y también un refill de mi Meloxicam de 15 mg. Además, necesito confirmar que todavía tienen Cigna como mi seguro en el sistema.

[AGENT]: What could I help you with today?

[PATIENT]: Necesito agendar mi cita de seguimiento para el tobillo, lo antes posible. Y también necesito un refill de mi receta, Meloxicam 15 mg. Ah, y quiero confirmar que mi seguro sigue siendo Cigna en su sistema.

[AGENT]: If you need help with appointments, medications, or have a question about the clinic, just let me know.
- **Expected Behavior:** Agent should recognize that speaker is using Spanish and refer to appropriate receptionist who can speak Spanish or help with their unique needs.

### Bug 5: Urgent Injury

- **Severity:** Medium
- **Call:** transcripts/urgent_injury_20260224_062848.txt
- **Timestamp:** 0:24
- **Description:** Agent should immediately refer patient to go to the ER or Urgent Care if the injury is significantly damaging or out of the scope of an orthopedics clinic.
- **Excerpt:**
[PATIENT]: Hi, I think I might have fractured my wrist. I fell pretty hard, and it's really swollen and painful. Can someone see me today, please?

[AGENT]: First, can you please tell me your date of birth? I'll check how soon we can get you in.

[PATIENT]: It's December 5, 1990. Please, I just really need to be seen today if possible!

[AGENT]: Thanks, Sarah. For a possible wrist fracture, you'll need a new patient consultation. Let me check for the earliest available appointment today. I'm not seeing any openings for a new patient consultation today or in the next week. Would you like to look for the soonest available appointment after that or try a different type of visit?
- **Expected Behavior:** Agent tells the patient later that they should go to the ER/urgent care later in the call, but this should be done before looking up the patient's information. Immediate patient needs should be addressed, then can ask for ID later after helping patient.

### Bug 6: Misprofile of Patient

- **Severity:** Low
- **Call:** transcripts/urgent_injury_20260224_062848.txt
- **Timestamp:** 0:37
- **Description:** Agent assumes the patient name is Sarah, even though the Date of Birth does not match the profile that the Agent created for Sarah in a previous call.
- **Excerpt**:
[AGENT]: First, can you please tell me your date of birth? I'll check how soon we can get you in.

[PATIENT]: It's December 5, 1990. Please, I just really need to be seen today if possible!

[AGENT]: Thanks, Sarah.
