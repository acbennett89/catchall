# M21-1, Part XI, Subpart i, Chapter 1, Section C  - Errors During Notice of Death (NOD) Processing

- Source: https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174195/
- Article ID: 554400000174195 (KMPR-174195)
- Last modified: 17 Dec 2025 14:21:42.000 +0000

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174194/)  [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174196/)

## Overview

---

**In This Section**

This section contains the following topics:

| **Topic** | **Topic Name** |
| --- | --- |
| 1 | [Erroneously Reported Deaths](#1) |
| 2 | [Incorrect Dates of Death](#2) |

---

## 1.  Erroneously Reported Deaths

---

**Introduction**

This topic contains information on erroneously reported deaths, including

* [updating the Veteran’s record when death was erroneous](#1a), and
* [actions to take if a spouse was erroneously paid the month of death (MOD) payment](#1b).

---

**Change Date**

December 17, 2025

---

**XI.i.1.C.1.a . Updating the Veteran’s Record When Death Was Erroneous**

Follow the steps in the table below after confirming

* a notice of death (NOD) was erroneous, and
* the Veteran is *not* deceased.

| **Step** | **Action** |
| --- | --- |
| 1 | Process a BENEFICIARY IDENTIFICATION AND RECORDS LOCATOR SUBSYSTEM (BIRLS) UPDATE to delete the following from the BIRLS record   * the date of death * the cause of death, and * any other erroneous information. |
| 2 | Establish an end product (EP) and take award action to resume any payments that were erroneously interrupted. |

***Reference***:  For more information on the EP and associated claim label to use when resuming a benefit erroneously terminated due to death, see

* [M21-4, Appendix B](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000011474/), and
* [M21-4, Appendix C](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000036570/).

---

**XI.i.1.C.1.b . Actions to Take if a Spouse Was Erroneously Paid the MOD Payment**

If a month of death (MOD) payment was paid in error because *either* the Veteran is not deceased *or* the MOD payment was not awarded to the appropriate spouse, then generate a non-entitlement award for the erroneous payment.

The finance activity will follow the standard debt collection procedures to recoup the erroneous payment.

***Note***:  Generate an award for the proper surviving spouse payee, when necessary.

---

## 2.  Incorrect Dates of Death

---

**Introduction**

This topic contains information on incorrect dates of death, including erroneous date of death

* [in the same month as the correct date of death](#2a)
* [not in the same month as the correct date of death](#2b), and
* later than the correct MOD and benefit checks are
  + [returned](#2c), and
  + [not returned](#2d).

---

**Change Date**

December 17, 2025

---

**XI.i.1.C.2.a . Erroneous Date of Death in Same Month as the Correct Date of Death**

Complete a BIRLS UPDATE to correct the date of death if the

* NOD was processed with an erroneous date of death, and
* erroneous date of death is in the same month as the correct date of death.

---

**XI.i.1.C.2.b . Erroneous Date of Death Not in the Same Month as the Correct Date of Death**

The system may establish an erroneous accounts receivable or erroneous accounts payable in the record if the

* NOD is processed with an incorrect date of death, and
* Veteran had a running award.

If an erroneous date of death is entered, follow the steps in the table below to take corrective action.

| **Step** | **Action** |
| --- | --- |
| 1 | Complete a BIRLS UPDATE to remove the incorrect date of death from BIRLS. |
| 2 | Establish an EP to correct the award termination date.    If the correct date of death is   * *after* the erroneous date of death, go to Step 3, or * *before* the erroneous date of death,    + process the termination from the correct date within the awards processing system, and   + go to Step 4 after the award is authorized. |
| 3 | Generate an award that   * reinstates benefits from the first of the month of the erroneously reported death, and * terminates benefits based on the correct date of death. |
| 4 | Complete a BIRLS UPDATE to correct the date of death in BIRLS. |

---

**XI.i.1.C.2.c . Erroneous Date of Death Later Than the Correct MOD and Benefit Checks Are Returned**

The system may establish a proceed due segment in the record if the

* FNOD is completed with a date of death that is later than the correct MOD, and
* Veteran’s uncashed benefit checks are returned.

If *all* the returned checks represent payment for the MOD or later:

* notify the finance activity to return the amount in proceeds to appropriations, and
* complete a BIRLS UPDATE to correct the date of death in BIRLS, if not already corrected.

---

**XI.i.1.C.2.d . Erroneous Date of Death Later Than the Correct MOD and Benefit Checks Are Not Returned**

Follow the steps in the table below if the

* FNOD is completed with a date of death that is later than the correct MOD, and
* Veteran’s benefit checks are *not* returned.

|  |  |
| --- | --- |
| **Step** | **Action** |
| 1 | Determine how much of an overpayment would have been created by entering the correct date of death. |
| 2 | Send a memorandum to the finance activity that   * explains that the overpayment resulted from an erroneous date of death in the system, and * requests a fiscal transaction to establish the accounts receivable. |
| 3 | Complete a BIRLS UPDATE to correct the date of death in BIRLS, if not already corrected. |

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174194/)  [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174196/)

[To Top](#top)
