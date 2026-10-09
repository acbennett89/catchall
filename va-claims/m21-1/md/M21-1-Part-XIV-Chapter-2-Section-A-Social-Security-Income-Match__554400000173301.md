# M21-1, Part XIV, Chapter 2, Section A - Social Security Income Match

- Source: https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173301/
- Article ID: 554400000173301 (KMPR-173301)
- Last modified: 10 Jun 2026 12:03:08.000 +0000

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173295/)  [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173303/)

## Overview

---

|  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | In This Section |  | This section contains the following topics:    |  |  | | --- | --- | | **Topic** | **Topic Name** | | 1 | [General Information on the Social Security Income Match](#1) | | 2 | [Processing Social Security Income Matches](#2) | | 3 | [Processing Verified Social Security Amounts: Old-Law and Section 306 Cases](#3) | |

---

## 1.  General Information on the Social Security Income Match

---

**Introduction**

This topic contains general information on the Social Security income match, including the

* [information sent to the Department of Veterans Affairs (VA) by the Social Security Administration (SSA)](#1a)
* [end product (EP) establishment](#1b), and
* [Social Security income match](#1c).

---

**Change Date**

July 7, 2022

---

**XIV.2.A.1.a . Information Sent to VA by SSA**

The Social Security Administration (SSA) periodically provides information on SSA rates for recipients of

* pension, and
* Parents’ Dependency and Indemnity Compensation (DIC).

---

**XIV.2.A.1.b . EP Establishment**

An end product (EP) 150 *PMC-Soc Sec Admn Match* with special issue *Upfront Verification* will be established by the system when a case is identified that requires correction based on a match with SSA payment data.

---

**XIV.2.A.1.c . Social Security Income Match**

The table below describes the stages of the Social Security income match and provides a description of the Department of Veterans Affairs (VA) initial actions.

| **Stage** | **Description** |
| --- | --- |
| 1 | VA receives a file from SSA containing SS income information for pension and Parents’ DIC recipients. |
| 2 | VA batch establishes an EP 150 *PMC-Soc Sec Admn Match* to control for income matches that contain discrepancies. |
| 3 | Claims processors pull detailed SSA payment data through the SSA INQUIRY function in the Veterans Benefits Management System (VBMS). |

---

## 2.  Processing Social Security Income Matches

---

**Introduction**

This topic contains information on processing verified Social Security amounts, including

* [SSA action](#2a)
* [Veterans Pension SSA matches](#2b)
* [Survivors Pension and Parents’ DIC cases](#2c), and
* [corrective award action necessary based on SSA matches](#2d).

---

**Change Date**

June 10, 2026

---

**XIV.2.A.2.a . SSA Action**

After matching VA records against SSA records, SSA informs VA of mismatched rates of income.

---

**XIV.2.A.2.b . Veterans Pension SSA Matches**

For each Veteran’s pension record, verification is attempted for

* the Veteran’s Social Security entitlement under their Social Security number (SSN), and
* a dependent’s entitlement under the Veteran’s SSN and under the dependent’s SSN.

---

**XIV.2.A.2.c . Survivors Pension and Parents’ DIC Cases**

For Survivors Pension and Parents’ DIC cases, verification is attempted under the Veteran’s SSN, the payee’s SSN, and any dependent’s SSN.

---

**XIV.2.A.2.d . Corrective Award Action Necessary Based on SSA Matches**

An EP 150 *PMC-Soc Sec Admn Match* is established by the system when a case is identified that requires action based on an income match with SSA.

Upon review of an income match, claims processors must pull detailed SSA payment data for the beneficiary and any applicable dependents through the SSA INQUIRY function in VBMS.  The results of this inquiry are limited.  If additional rates are needed to complete the review, use the SSA Retro Calculator to determine earlier rates.  The calculator is located under the Business Management Section of [Pension and Fiduciary’s Intranet page](https://vbaw.vba.va.gov/pensionandfiduciary/pension/index.asp).

Use the table below to determine the action(s) to take when the SSA income in the VA record is different than the verified Social Security rate by $1 or more.

|  |  |
| --- | --- |
| **If the verified Social Security rate is ...** | **Then ...** |
| * higher than the rate(s) VA counted, and * correcting the rate(s) will result in decreased VA benefits | * calculate income for VA purposes (IVAP) based on the verified Social Security rate(s) effective the date of the income change, or the date the award began, whichever is later * clear the EP 150 * establish EP 600 *PMC-SSA Match*, with special issue *Upfront Verification*, follow the due process procedures to include notice of proposed adverse action found in [M21-1, Part X, Subpart ii, 3.A](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177965/), and * advise the payee of the monthly Social Security rate(s)    + that SSA has reported, and   + on which VA benefits have been paid. |
| * higher than the rate VA is counting, and * using the verified rate will ***not*** result in an overpayment or decreased VA benefits | * use the verified rate to calculate IVAP * use the EP 150 to update the award with the verified Social Security rate, and * inform the beneficiary of the action taken. |
| * lower than the rate VA is counting, and * the claimant reported a Social Security rate that is a reason for the discrepancy | * continue to use the rate reported by the beneficiary and the corresponding VA calculated cost-of-living adjustments (COLAs) where applicable to compute IVAP, and * provide notice to the beneficiary with    + information about the Social Security rate used to calculate benefits   + information about the discrepancy with income reported by SSA, and   + the appropriate standard form for reporting an income change.   ***Reference***:  For information on standard forms for income changes, see [M21-1, Part IX, Subpart i, 3.B.2](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000178517/). |
| * lower than the rate VA is counting, and * a VA computed SS COLA is the only reason for the discrepancy | * calculate IVAP based on the verified Social Security rate * use the EP 150 to update the award with the verified Social Security rate * if applicable, increase VA benefits, and * provide notice to the beneficiary.   ***Note***:  If using the verified Social Security rate results in an increase in the pension rate, refer to [M21-1, Part IX, Subpart iii, 1.H.1.b](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177523/) for time limits and effective date procedures to increase pension based on a change in income. |

***Note***:  Do not contact SSA for income information via fax, e-mail, telephone, etc., unless the claimant submits a written request that VA do so.

***References***:  For more information on

* SSA COLA calculations, see [M21-1, Part IX, Subpart iii, 1.B.3.g](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177517/), and
* actions to take if a beneficiary alleges SSA information is inaccurate, see [M21-1, Part IX, Subpart iii, 1.B.4.a](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177517/).

---

## 3.  Processing Verified Social Security Amounts:  Old-Law and Section 306 Cases

---

**Introduction**

This topic contains information on processing verified Social Security amounts in Old-Law and Section 306 cases, including

* [Old-Law and Section 306 cases](#3a), and
* [audits of protected pension cases after SSA matches](#3b).

---

**Change Date**

July 7, 2022

---

**XIV.2.A.3.a . Old-Law and Section 306 Cases**

In all Old-Law and Section 306 cases for which Social Security data is available, the INCOME/EXPENSES/NETWORTH screen within the AWARDS/RATING tab of the corporate record is updated when there is a COLA to show the VA computed Social Security income amounts for beneficiaries and dependents.

***Reference***:  For more information on the data stored in the corporate record, see the *Share Online Help*.

---

**XIV.2.A.3.b . Audits of Protected Pension Cases After SSA Matches**

The VA system does not generate an EP in protected pension cases merely because there are discrepancies between the Social Security amounts returned by the SSA and the existing amounts in the corporate record (the amount in the corporate record is the VA computed post-COLA Social Security rate).

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173295/)  [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000173303/)

[To Top](#top)
