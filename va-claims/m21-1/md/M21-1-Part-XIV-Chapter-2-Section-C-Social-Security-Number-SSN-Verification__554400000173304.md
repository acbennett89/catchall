# M21-1, Part XIV, Chapter 2, Section C - Social Security Number (SSN) Verification

- Source: https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173304/
- Article ID: 554400000173304 (KMPR-173304)
- Last modified: 29 May 2025 19:50:57.000 +0000

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173303/) [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173919/)

## Overview

---

**In This Section**

This section contains the following topics:

| **Topic** | **Topic Name** |
| --- | --- |
| 1 | [Overview of the Verification Process](#1) |
| 2 | [Processing Unverified SSNs](#2) |
| 3 | [Actions to Take If Attempts to Verify an SSN Using Information of Record Are Unsuccessful](#3) |
| 4 | [SSN Verification Codes in the Beneficiary Identification and Records Locator Subsystem (BIRLS)](#4) |

---

## 1.  Overview of the Verification Process

---

**Change Date**

January 10, 2022

---

**XIV.2.C.1.a . Overview of the Verification Process**

Each month, the Department of Veterans Affairs (VA) runs a computerized records-matching program that compares the Social Security numbers (SSNs) associated with 25 percent of all VA file numbers with the SSNs in Social Security Administration (SSA) records.  By doing so, VA is able to check the accuracy of the SSNs associated with all file numbers three times each year.

* When verification of an SSN is *successful*,

  + computer programming automatically initiates the entry of *Y* in the SSN – VERIFIED field in the Beneficiary Identification and Records Locator Subsystem (BIRLS), and
  + no regional office (RO) action is required.
* When verification of an SSN is *unsuccessful*,

  + the Veterans Benefits Management System (VBMS) generates a work item that is distributed by the National Work Queue, and
  + the station of origination must take the actions described in [M21-1, Part XIV, 2.C.2](#2).

***Reference***:  For more information on SSN verification codes in the corporate record, see [M21-1, Part XIV, 2.C.4](#4).

---

## 2.  Processing Unverified SSNs

---

**Introduction**

This topic contains information on processing unverified SSNs, including

* [Unverified Social Security Numbers work item information](#2a)
* [processing work item 834D](#2b)
* [action to take when the Federal On-Line Query (FOLQ) system returns a child’s date of birth (DOB) that differs from the DOB in VA’s corporate record](#2c)
* [processing work item 834E](#2d), and
* [actions to take upon discovering an individual’s name in VA records does not match the same individual’s name in SSA records](#2e).

---

**Change Date**

January 10, 2022

---

**XIV.2.C.2.a . Unverified SSNs Work Item Information**

The table below contains a description of the two work items that are created based on the Unverified Social Security Numbers matching program.

| **Work Item Code** | **Name** | **Description** |
| --- | --- | --- |
| *834D* | *SSN NOT IN FILE* | SSA did not issue the SSN in the VA record. |
| *834E* | *SSN DOES NOT MATCH* | Identifying information in VA records does not match SSA records.    ***Note***:  This does not necessarily mean the SSN is incorrect. |

---

**XIV.2.C.2.b . Processing Work Item 834D**

Follow the instructions in the table below for each work item 834D.

| **Step** | **Action** |
| --- | --- |
| 1 | Establish end product (EP) 692. |
| 2 | Follow the instructions in the [*VBMS Core User Guide*](http://vbaw.vba.va.gov/VBMS/Resources_Technical_Information.asp) for making an SSA inquiry through SSA’s Federal On-Line Query (FOLQ) system. |
| 3 | Follow the instructions in the table below.     | **If …** | **Then …** | | --- | --- | | FOLQ returns an SSN and DOB that match the SSN and date of birth (DOB) in VA’s corporate record | clear the pending EP 692. | | * the unverified SSN belongs to a Veteran, and * FOLQ returns an SSN that does *not* match the SSN in VA’s corporate record | * refer the case to the station duplicate record coordinator to   + resolve a potential duplicate record, and   + request correction of the SSN, and * clear the pending EP 692. | | * the unverified SSN belongs to a Veteran, and * FOLQ returns a DOB that differs from the DOB in VA’s corporate record | * attempt to determine the correct DOB by    + reviewing the claims folder, and/or   + contacting the beneficiary by telephone * use the BIRLS UPDATE command in Share to correct the DOB (if the DOB in VA’s corporate record is incorrect), and * clear the pending EP 692. | | * the unverified SSN belongs to a Veteran’s dependent, and * FOLQ returns an SSN that does *not* match the SSN in VA’s corporate record | * update the corporate record by entering the SSN obtained through FOLQ in the SSN field on the    + DEPENDENTS screen in Share, or   + DEPENDENCY screen in VBMS Awards (VBMS-A), and * clear the pending EP 692. | | * the unverified SSN belongs to a Veteran’s spouse, and * FOLQ returns a DOB that differs from the DOB in VA’s corporate record | * attempt to determine the correct DOB by    + reviewing the claims folder, and/or   + contacting the beneficiary by telephone * enter the correct DOB (if the DOB in VA’s corporate record is incorrect) on the    + DEPENDENTS screen in Share, or   + DEPENDENCY screen in VBMS-A, and * clear the pending EP 692. | | * the unverified SSN belongs to a Veteran’s child, and * FOLQ returns a DOB that differs from the DOB in VA’s corporate record | follow the instructions in [M21-1, Part XIV, 2.C.2.c](#2c).    ***Exception***:  Follow the instructions in the *preceding* row for updating the corporate record if VA   * has determined the child is permanently incapable of self-support, and * did *not* pay additional benefits for the child as a school child *prior* to determining the child was permanently incapable of self-support. | | FOLQ is unable to locate an SSA record | * attempt to obtain identifying information that differs from the information in VA’s corporate record, by    + reviewing the claims folder   + contacting the beneficiary by telephone, and/or   + using available, web-based, address locator services, to include those for which VA pays a fee for access * use the new identifying information (if obtained) to make additional SSA inquiries through FOLQ, and * follow the instructions in [M21-1, Part XIV, 2.C.3.a](#3a) if    + attempts to obtain new identifying information are unsuccessful, or   + FOLQ is unable to locate an SSA record despite the entry of new identifying information into VBMS Core.   ***Note***:  Follow the instructions in [M21-1, Part III, Subpart i, 2.D.1.e](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000033257/) when requesting information from a beneficiary by telephone. | |

***References***:  For more information on

* FOLQ, see [M21-1, Part III, Subpart ii, 1.B.3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000014111/), and
* using
  + Share, see the [*Share User Guide*](http://css.vba.va.gov/SHARE/), and
  + VBMS-A, see the *[VBMS Awards User Guide](http://vbaw.vba.va.gov/VBMS/Resources_Technical_Information.asp)*.

---

**XIV.2.C.2.c . Action to Take When FOLQ Returns a Child’s DOB That Differs From the DOB in VA’s Corporate Record**

Follow the instructions in the table below when

* an 834D work item is received
* the unverified SSN belongs to a Veteran’s child
* the child is *not* permanently incapable of self-support by VA rating (or, if VA determined the child *is* permanently incapable of self-support, VA paid additional benefits for the child as a school child *prior* to making that determination), and
* FOLQ returns a DOB for the child that differs from the DOB in VA’s corporate record.

| **Step** | **Action** |
| --- | --- |
| 1 | Clear the pending EP 692. |
| 2 | Does a review of the claims folder reveal a DOB for the child that differs from the DOB in the corporate record?   * If *yes*, go to the next step. * If *no*, go to Step 6. |
| 3 | Using the DOB identified in the preceding step, submit another SSA inquiry through FOLQ. |
| 4 | Did FOLQ return a DOB that matches the DOB identified in the claims folder?   * If *yes*, go to the next step. * If *no*, go to Step 6. |
| 5 | Follow the instructions in [M21-1, Part VI, Subpart i, 2.B.3.f and (when applicable) g](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000179474/).  Afterward, go to Step 20 of this table. |
| 6 | Establish EP 130, using the current date as the date of claim. |
| 7 | Attempt to contact the beneficiary by telephone for the purpose of confirming the child’s DOB. |
| 8 | Were attempts to contact the beneficiary by telephone successful?   * If yes, go to the next step. * If no, go to Step 12.   ***Note***:  Follow the instructions in [M21-1, Part III, Subpart i, 2.D.1.e and f](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000033257/) when obtaining or attempting to obtain information from a beneficiary by telephone. |
| 9 | Did the beneficiary provide a DOB that differs from the DOB in the corporate record?   * If *yes*, go to the next step. * If *no*, go to Step 12. |
| 10 | Using the DOB identified in the preceding step, submit another SSA inquiry through FOLQ. |
| 11 | Did FOLQ return a DOB that matches the DOB the beneficiary provided in Step 9?   * If *yes*,    + generate and authorize an award that corrects the DOB, and   + go to Step 19. * If *no*, go to the next step. |
| 12 | * Clear the pending EP 130. * Establish EP 600. |
| 13 | Prepare a notice of proposed adverse action that   * asks the beneficiary to provide VA with a copy of the child’s birth certificate, and * informs the beneficiary that    + VA will remove the child from the beneficiary’s award if the beneficiary does not return the form within 60 days, and   + the effective date of the award adjustment, if made, will be the first of the month following the end of the 60-day response period, per [38 CFR 3.500(w)](https://www.ecfr.gov/cgi-bin/text-idx?SID=54a225dcfce3f8ad240f594061b9f5a9&mc=true&node=se38.1.3_1500&rgn=div8). |
| 14 | Did the beneficiary provide the child’s birth certificate within 65 days?   * If *yes*, go to Step 15. * If *no*,    + remove the child from the beneficiary’s award as proposed in Step 13   + notify the beneficiary of the action taken, and   + go to Step 20.   ***Note***:  Follow the instructions in [M21-1, Part X, Subpart ii, 3.B.3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177966/) if the beneficiary requests a hearing in response to the notice of proposed adverse action. |
| 15 | Does the DOB on the birth certificate match the DOB in the corporate record?   * If *yes*, go to Step 17. * If *no*, go to the next step. |
| 16 | * Generate and authorize an award that updates the corporate record to reflect the DOB on the birth certificate. * Go to Step 19. |
| 17 | Clear the pending EP 600. |
| 18 | Go to Step 20 *after*   * notifying the beneficiary that VA has used the birth certificate to confirm the accuracy of the child’s DOB in VA’s records, and * encouraging the beneficiary to notify SSA that its records contain an incorrect DOB for the child. |
| 19 | Notify the beneficiary of the action taken.    ***Note***:  If the correct DOB is *later* than the DOB previously entered in the corporate record, also notify the beneficiary of any additional benefits to which they may be entitled by virtue of the action taken.    ***Example***:  A school child dropped off a beneficiary’s award at age 23 based on a DOB in the corporate record of August 2, 1993.  The correct DOB, however, is August 2, 1994.  The beneficiary may be entitled to additional benefits for the child if the beneficiary submits *[VA Form 21-674, Request for Approval of School Attendance](http://www.vba.va.gov/pubs/forms/VBA-21-674-ARE.pdf)*, showing the child remained in school beyond August 2, 2016. |

***References***:  For more information on

* determinations regarding a child’s capacity for self-support, see [M21-1, Part X, Subpart ii, 6.B](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177975/), and
* issuing a notice of proposed adverse action, see [M21-1, Part X, Subpart ii, 3.A](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177965/).

---

**XIV.2.C.2.d . Processing Work Item 834E**

Follow the instructions in the table below when an 834E work item is received.

| **Step** | **Action** |
| --- | --- |
| 1 | Establish EP 692. |
| 2 | Attempt to obtain identifying information that differs from the information that appears on the work itemby   * reviewing the claims folder, and * contacting the beneficiary by telephone.   ***Note***:  Follow the instructions in [M21-1, Part III, Subpart i, 2.D.1.e](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000033257/) when requesting information from a beneficiary by telephone. |
| 3 | Were attempts to obtain new identifying information successful?   * If *yes*, go to the next step. * If *no*,    + disregard the remaining steps in this table, and   + follow the instructions in [M21-1, Part XIV, 2.C.3.a](#3a). |
| 4 | Using the new identifying information referenced in Step 2, follow the instructions in the [*VBMS Core User Guide*](http://vbaw.vba.va.gov/VBMS/Resources_Technical_Information.asp) for making an SSA inquiry through FOLQ. |
| 5 | Follow the instructions in the table below.     | **If …** | **Then …** | | --- | --- | | * the unverified SSN belongs to a Veteran, and * FOLQ returns an SSN that does *not* match the SSN in VA’s corporate record | * refer the case to the station duplicate record coordinator to    + resolve the potential duplicate record, and   + request correction of the SSN, and * clear the pending EP 692. | | * the unverified SSN belongs to a Veteran’s dependent, and * FOLQ returns an SSN that does *not* match the SSN in VA’s corporate record | * update the corporate record by entering the SSN obtained through FOLQ in the SSN field on the    + DEPENDENTS screen in Share, or   + DEPENDENCY screen in VBMS-A, and * clear the pending EP 692. | | FOLQ is unable to locate an SSA record | follow the instructions in [M21-1, Part XIV, 2.C.3.a](#3a). | |

***References***:  For more information on

* FOLQ, see [M21-1, Part III, Subpart ii, 1.B.3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000014111/), and
* using
  + Share, see the [*Share User Guide*](http://css.vba.va.gov/SHARE/), and
  + VBMS-A, see the *[VBMS Awards User Guide](http://vbaw.vba.va.gov/VBMS/Resources_Technical_Information.asp)*.

---

**XIV.2.C.2.e . Actions to Take Upon Discovering an Individual’s Name in VA Records Does Not Match the Same Individual’s Name in SSA Records**

Follow the instructions in the table below if, during the course of verifying an individual’s SSN, it is discovered that an individual’s name in VA records does not match the same individual’s name in SSA records.

***Important***:  The following do ***not*** constitute a mismatch in names:

* a minor difference in the spelling of a name
* a different last name that can be attributed to an individual’s marriage or divorce, and
* a different first name that can be attributed to an individual’s use of a widely recognized nickname.

***Examples***:

* A first name spelled “Michelle” in VA records does not constitute a mismatch if it is spelled “Michele” in SSA records.
* “Bob” is a widely recognized nickname for “Robert.”
* “Bill” is a widely recognized nickname for “William.”

| **Step** | **Action** |
| --- | --- |
| 1 | Establish EP 692 (if the EP is not already pending). |
| 2 | Attempt to contact the beneficiary by telephone and ask him/her to explain why the individual in question has a name in VA records that differs from the same individual’s name in SSA records.    ***Notes***:   * Follow the instructions in [M21-1, Part III, Subpart i, 2.D.1.e](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000033257/) when requesting information from a beneficiary by telephone. * [M21-1, Part II, Subpart iii, 3.B.4](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174882/) describes the evidence that must be of record to warrant updating VA records with a different name for a ***beneficiary***.  Request this evidence from the beneficiary if they report a change in name. |
| 3 | Were attempts to contact the beneficiary by telephone successful?   * If *yes*, go to the next step. * If *no*, go to Step 10. |
| 4 | Was a credible explanation for the difference in names obtained from the beneficiary?   * If *yes*, go to the next step. * If *no*,    + add *Potential Under/Overpayment* as a special issue under the EP 692, and   + go to Step 19. |
| 5 | Is adjustment of the beneficiary’s award necessary based on the explanation the beneficiary gave?   * If *yes*, go to the next step. * If *no*, go to Step 8. |
| 6 | * Clear the pending EP 692. * Establish EP 130. * Add *Potential Under/Overpayment* as a special issue. |
| 7 | Adjust the beneficiary’s award, based on the facts found, under the pending EP 130 and go to Step 29. |
| 8 | Update VA’s computer system to reflect the correct name, if necessary. |
| 9 | Clear the pending EP 692 and disregard the remaining steps in this table. |
| 10 | Add *Potential Under/Overpayment* as a special issue under EP 692. |
| 11 | Prepare and send a development letter to the beneficiary.   * Ask the beneficiary to explain why the individual in question has a name in VA records that differs from the same individual’s name in SSA records. * If the ***beneficiary’s*** name differs from the name in SSA records, ask the beneficiary to provide the evidence referenced in [M21-1, Part II, Subpart iii, 3.B.4.b](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174882/), if the beneficiary has changed their name. * Inform the beneficiary that if VA does not receive a response to its request within 30 days, VA may reduce or discontinue benefits. |
| 12 | Did the beneficiary respond within 30 days with a credible explanation for the difference in names?   * If *yes*, go to the next step. * If *no*, go to Step 19. |
| 13 | Is adjustment of the beneficiary’s award necessary based on the explanation the beneficiary gave?   * If *yes*, go to the next step. * If *no*, go to Step 16. |
| 14 | * Clear the pending EP 692. * Establish EP 130. * Add *Potential Under/Overpayment* as a special issue. |
| 15 | Adjust the beneficiary’s award, based on the facts found, under the pending EP 130 and go to Step 29. |
| 16 | Update VA’s computer system to reflect the correct name, if necessary. |
| 17 | Clear the pending EP 692. |
| 18 | * Notify the beneficiary that, based on the response to the development letter referenced in Step 11, VA will make no adjustments to the award. * Disregard the remaining steps in this table. |
| 19 | Clear the pending EP 692. |
| 20 | Establish EP 600, using the *SS Number Verification* claim label, and add *Potential Under/Overpayment* as a special issue. |
| 21 | Prepare and send a notice of proposed adverse action to the beneficiary.  In the notice, inform the beneficiary that   * VA intends to reduce or discontinue benefits (whichever is appropriate) based on the beneficiary’s failure to provide a credible explanation as to why the individual in question has a name in VA records that differs from the same individual’s name in SSA records, and * the effective date of any award adjustment that is based on the beneficiary’s failure to provide the referenced explanation will be first of the month following the month during which the 60-day period following the date VA first requested the explanation expires, per [38 CFR 3.500(w)](https://www.ecfr.gov/cgi-bin/text-idx?SID=e90b594229311d411bb678530a40d388&mc=true&node=se38.1.3_1500&rgn=div8).   ***Reference***:  For more information on issuing notice of a proposed adverse action, see [M21-1, Part X, Subpart ii, 3.A](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177965/). |
| 22 | Did the beneficiary respond within 65 days with a credible explanation for the difference in names?   * If *yes*, go to the next step. * If *no*, go to Step 28.   ***Note***:  Follow the instructions in [M21-1, Part X, Subpart ii, 3.B.3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177966/) if the beneficiary requests a hearing in response to the notice of proposed adverse action. |
| 23 | Is adjustment of the beneficiary’s award necessary based on the explanation the beneficiary gave?   * If *yes*, go to the next step. * If *no*, go to Step 25. |
| 24 | Adjust the beneficiary’s award, based on the facts found, under the pending EP 600 and go to Step 29. |
| 25 | Update VA’s computer system to reflect the correct name, if necessary. |
| 26 | Notify the beneficiary that, based on the response to the notice of proposed adverse action, no adjustment to the award is necessary. |
| 27 | * Clear the pending EP 600. * Disregard the remaining steps in this table. |
| 28 | Reduce or discontinue (whichever is appropriate) the beneficiary’s award effective the date proposed in Step 21. |
| 29 | Notify the beneficiary of the action taken. |

---

## 3.  Actions to Take If Attempts to Verify an SSN Using Information of Record Are Unsuccessful

---

**Change Date**

January 31, 2022

---

**XIV.2.C.3.a . Actions to Take If Attempts to Verify an SSN Using Information of Record Are Unsuccessful**

Follow the instructions in the table below if attempts to verify an individual’s SSN through the means described in [M21-1, Part XIV, 2.C.2.b](#2b) or [d](#2d) are *unsuccessful*.

| **Step** | **Action** |
| --- | --- |
| 1 | Add *Potential Under/Overpayment* as a special issue under the pending EP 692. |
| 2 | Prepare a development letter that is addressed to the beneficiary whose VA record contains information that SSA cannot verify.  In the letter,   * inform the beneficiary that SSA could not verify information contained in the VA record * explain that [38 U.S.C. 5101](https://www.law.cornell.edu/uscode/text/38/5101) requires beneficiaries to provide VA with a correct SSN for themselves and their dependent(s) * ask the beneficiary to provide the identifying information VA requires (first and last name, SSN, and DOB) to verify the SSN in question, and * advise the beneficiary that if a response is not received within 60 days, VA may reduce or discontinue benefits.   ***Important***:  Ask the beneficiary to provide ***documentary*** evidence (such as a copy of the individual’s Social Security card and/or birth certificate) of the identifying information VA requires to verify the SSN in question if, during the course of the procedure described in [M21-1, Part XIV, 2.C.2.b](#2b) or [d](#2d),   * the beneficiary confirmed the accuracy of the identifying information VA already has of record, but * FOLQ is unable to locate an SSA record when a claims processor submits an SSA inquiry using the identifying information of record. |
| 3 | Did the beneficiary respond to the development letter within 60 days?   * If *yes*, go to the next step * If *no*,    + clear the EP 692, and   + go to Step 7. |
| 4 | Take whatever action is necessary based on the information the beneficiary provided in response to the development letter. |
| 5 | Inform the beneficiary that VA will not reduce or discontinue the award (unless the beneficiary’s response to the notice of proposed adverse action necessitates an award adjustment). |
| 6 | Clear the pending EP 692.  No further actions in this table are required. |
| 7 | Establish EP 600, using the *SS Number Verification* claim label, and add *Potential Under/Overpayment* as a special issue. |
| 8 | Prepare and send a notice of proposed adverse action to the beneficiary.  In the notice, inform the beneficiary that   * VA intends to reduce or discontinue benefits (whichever is appropriate) based on the beneficiary’s failure to provide the information VA requested in the development letter referenced in Step 2, and * the effective date of any award adjustment that is based on the beneficiary’s failure to provide the information VA requested will be the first of the month following the month during which the 60-day period following the date VA first requested the information expires, per [38 CFR 3.500(w)](https://www.ecfr.gov/cgi-bin/text-idx?SID=e90b594229311d411bb678530a40d388&mc=true&node=se38.1.3_1500&rgn=div8).   ***Reference***:  For more information on issuing notice of a proposed adverse action, see [M21-1, Part X, Subpart ii, 3.A](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177965/). |
| 9 | Did the beneficiary respond within 65 days?   * If *yes*, go to the next step. * If *no*, go to Step 13.   ***Note***:  Follow the instructions in [M21-1, Part X, Subpart ii, 3.B.3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177966/) if the beneficiary requests a hearing in response to the notice of proposed adverse action. |
| 10 | Take whatever action is necessary based on the information the beneficiary provided in response to the notice of proposed adverse action. |
| 11 | Inform the beneficiary that VA will not reduce or discontinue the award (unless the beneficiary’s response to the notice of proposed adverse action necessitates an award adjustment). |
| 12 | Clear the pending EP 600.  No further actions in this table are required. |
| 13 | Reduce or discontinue (whichever is appropriate) the beneficiary’s award effective the date proposed in Step 8. |
| 14 | Notify the beneficiary of the action taken. |

---

## 4.SSN Verification Codes in BIRLS

---

**Introduction**

This topic contains information on SSN verification codes in BIRLS, including

* [code descriptions](#4a), and
* [updating the corporate record to reflect the verification of an SSN](#4b).

---

**Change Date**

April 20, 2017

---

**XIV.2.C.4.a . Code Descriptions**

BIRLS displays the two codes referenced in the table below, which indicate whether or not VA has verified the SSN of a Veteran or a Veteran’s spouse.

| **Verification Code** | **Description** |
| --- | --- |
| *Y* | VA verified the SSN through computerized records-matching with SSA. |
| *N* | VA has not verified the SSN. |

---

**XIV.2.C.4.b . Updating the Corporate Record to Reflect the Verification of an SSN**

If an RO has proof that the SSN in a VA record is correct, an RO employee may enter *Y* in the SSN - VERIFIED field in BIRLS.

Proof consists of a

* copy of the individual’s Social Security card
* printout of a response to a FOLQ query that verifies the SSN, or
* letter from SSA that verifies the SSN in question.

***References***:  For more information on

* updating BIRLS, see the *[Share User Guide](http://css.vba.va.gov/SHARE/)*, and
* submitting an SSA inquiry through FOLQ, see the [*VBMS Core User Guide*](http://vbaw.vba.va.gov/VBMS/Resources_Technical_Information.asp).

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173303/) [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173919/)

[To Top](#top)
