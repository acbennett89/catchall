# M21-1, Part II, Subpart ii, Chapter 1, Section A - Establishing New and Converting Old Claims Folders

- Source: https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174863/
- Article ID: 554400000174863 (KMPR-174863)
- Last modified: 18 Dec 2025 16:19:18.000 +0000

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174861/)   [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174864/)

Overview

---

**In This Section**

This section contains the following topics:

| Topic | Topic Name |
| --- | --- |
| 1 | [Assigning Claims Folder Numbers and Establishing Claims Folders](#1) |
| 2 | [Claims Folder Formats](#2) |

---

## 1.  Assigning Claims Folder Numbers and Establishing Claims Folders

---

**Introduction**

This topic contains information about the assignment of claims folder numbers and establishing claims folders, including

* [associating records with a claims folder number](#1a)
* [how claims folders and numbers are established](#1b)
* [checking for a previously established or duplicate claims folder number](#1c), and
* [handling missing or discrepant Beneficiary Identification and Records Locator Subsystem (BIRLS) and corporate records](#1d).

---

**Change Date**

December 17, 2025

---

**II.ii.1.A.1.a . Associating Records With a Claims Folder Number**

All records for claimants and beneficiaries that can be identified must be associated with a claims folder number and stored in the corresponding claims folder.  There are two types of claims folder numbers used by the Veterans Benefits Administration (VBA) to establish the claims folder.  The numbers are based on

* the Veteran’s Social Security number (SSN), or
* an eight-digit claims folder number assigned through the Beneficiary Identification and Records Locator Subsystem (BIRLS).

Use the table below to determine the type of claims folder number to assign.

| **For original applications from …** | **The claims folder number is based on …** |
| --- | --- |
| Veterans with an established SSN | the SSN. |
| * Philippine nationals, and * other Veterans without an established SSN | BIRLS assignment. |

***Important***:

* All documents received by VBA with identifying personal information require association with a claims folder number regardless of the need for claims establishment or confirmation of Veteran status.
* To avoid duplicate claim (DUPC) processing, conduct a thorough search of all systems for a previously established claims folder number as outlined in   [M21-1, Part II, Subpart ii, 1.A.1.c](#1c).

---

**II.ii.1.A.1.b . How Claims Folders and Numbers Are Established**

Veteran data is electronically sent from the Department of War to VBA and used to establish a corporate record for the individual.  The establishment of the corporate record automatically creates the corresponding electronic claims folder (eFolder).

Historically, claims processors had to manually generate the claims folder number and paper claims folders via legacy applications used to establish claims, update system information, and track folders.

***Reference***:  For more information on historical procedures for creating claims folders and numbers, see the attachments

* *Historical\_M21-1III\_ii\_3\_SecA\_6-27-16*, and
* *Historical\_M21-1III\_ii\_3\_SecB\_2-14-20*.

---

**II.ii.1.A.1.c . Checking for a Previously Established or Duplicate Claims Folder Number**

When processing mail or taking other claim actions, it may be necessary to determine if a claims folder had been previously established under another claims folder number and reconciliation of the records is needed.

The table below provides guidance on checking for the existence of a previously established or duplicate claims folder number.

| **Step** | **Action** |
| --- | --- |
| 1 | Review the correspondence for the BIRLS-generated eight-digit number or an SSN used as a claims folder number.    If a claims folder number   * is *available*, use the SEARCH ALL IN LIST command in Share to pull up the claimant’s data for review, or * is *not available*, attempt to locate the claimant in VBA systems using information from the correspondence and alternative data sources, including    + Veterans Benefits Management System (VBMS) advanced profile search   + Share BIRLS INQUIRY command   + Share CORPORATE INQUIRY command   + Participant Profile PERSON and NUMBERS searches in Share   + Compensation and Pension Record Interchange (CAPRI) enterprise search, and   + non-Department of Veterans Affairs (VA) sources, such as      - CLEAR     - Defense Finance and Accounting Service - Retired and Casualty Pay System, and     - Federal On-line Query (FOLQ), which can be accessed through the SSA INQUIRY in VBMS.   ***Note***:  If the claims folder number cannot be obtained using alternative sources, go to Step 3. |
| 2 | Review the SEARCH ALL IN LIST results and verify that the claimant has both a BIRLS record and corporate record listed under the claims folder number.    If   * a BIRLS and corporate record both exist under the claims folder number, no further action in this table is necessary, or * a BIRLS or corporate record is missing, or the records exist under separate claims folder numbers (i.e. one under the eight-digit BIRLS number, the other using the claimant’s SSN), follow the guidance in [M21-1, Part II, Subpart ii, 1.A.1.d](#1d).   ***Note***:  If the Veteran reports that their SSN has been changed, complete a search using the old SSN. |
| 3 | Contact the claimant using information provided on the correspondence or obtained via alternative data sources indicated in Step 1, and obtain the missing information required to validate the claims folder number, or if necessary, establish a new record.    If the claimant cannot be reached, continue processing the   * correspondence as unidentifiable mail, as instructed in [M21-1, Part II, Subpart i, 2.C.5](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174860/), or * claim under the assumption that there is not a previously established or duplicate claims folder that must be reconciled. |

***References***:  For more information on

* CAPRI search functions, see the [*CAPRI User Manual*](https://www.va.gov/vdl/application.asp?appid=133), and
* advanced search features in VBMS, see the *VBMS Core User Guide*.

---

**II.ii.1.A.1.d . Handling Missing or Discrepant BIRLS and Corporate Records**

Use the table below to determine what steps to take when it is necessary to handle missing or discrepant BIRLS and corporate record data.

| **If ...** | **Then ...** |
| --- | --- |
| a BIRLS record is missing | * follow the guidance in the *[Duplicate Record Consolidation Materials](https://vbaw.vba.va.gov/bl/21/publicat/Users/Index.htm#bmd)* to prevent duplicate record creation and, if directed, * use the BIRLS ADD command in Share to create the BIRLS record.   ***Note***:  Review the ALL RELATIONSHIPS tab in the CORPORATE record – the claimant may have a corporate record as a dependent, who is now seeking benefits related to their own military service. |
| corporate record is missing | use the BIRLS UPDATE command in Share to create the corporate record.    ***Notes***:   * The minimum information required to create a corporate record includes the    + SSN and/or eight-digit BIRLS claim number   + first name   + last name, and   + date of birth. * If the minimum information required cannot be obtained via the alternative data sources or claimant contact discussed in [M21-1, Part II, Subpart ii, 1.A.1.c](#1c), Steps 1-3, process the correspondence as unidentifiable mail. |
| a BIRLS and corporate record both exist but under different claims folder numbers | follow the duplicate claim processing guidance in the *[Duplicate Record Consolidation Materials](https://vbaw.vba.va.gov/bl/21/publicat/Users/Index.htm#bmd)*. |

---

## 2.  Claims Folder Formats

---

**Introduction**

This topic contains information on the format of claims folders, including

* [claims folder formats](#2a)
* definition of

  + [an eFolder](#2b), and
  + [a paper claims folder](#2c)
* [eFolder locations](#2d)
* [end products (EPs) that require scanning of unconverted paper claims folders](#2e)
* [determining if a scanning request is necessary](#2f)
* [resolving claims folder format discrepancies](#2g), and
* [claims folder related flashes](#2h).

---

**Change Date**

March 17, 2025

---

**II.ii.1.A.2.a . Claims Folder Formats**

VBA has two formats for claims folders:

* eFolders, and
* paper claims folders.

While some paper claims folders still exist, all new claims folders are established in the electronic format unless explicitly stated as an exception.

---

**II.ii.1.A.2.b . Definition: eFolder**

An ***electronic claims folder*** (eFolder) is an electronic repository for scanned documents related to a single Veteran and associated with a claims folder number.  VA maintains eFolders inVBMS.

***References***:  For more information on

* VBMS eFolders, see the *VBMS Core User Guide*, and
* claims folder numbers, see [M21-1, Part II, Subpart ii, 1.A.1](#1).

---

**II.ii.1.A.2.c . Definition: Paper Claims Folder**

A ***paper claims folder*** is a repository for paper documents related to a single Veteran and associated with a claims folder number.  VBA has two types of paper claims folders:

* claims folders, and
* notice of death folders.

***Important***:

* A paper claims folder that has been scanned and uploaded to an electronic record system (i.e. converted) is thereafter considered an eFolder, unless the folder in storage is explicitly referenced.
* Most paper claims folders not currently located at a Federal records center (FRC) are stored at a scanning facility and have already been converted to eFolders or are queued to be converted.

***Reference***:  For more information on claims folder numbers, see [M21-1, Part II, Subpart ii, 1.A.1](#1).

---

**II.ii.1.A.2.d . eFolder Locations**

VBA uses the folder locations listed in the table below when a(n)

* paper claims folder is sent for scanning conversion, or
* eFolder is established and no paper claims folder previously existed.

| **Folder Location** | **Description** |
| --- | --- |
| DCSC1 | Converted and stored at CSRA Newnan, GA. |
| DCSC2 | Converted and stored at CSRA Mt Vernon, KY. |
| DCSS1 | Converted and stored at SMS Janesville, WI. |
| DCSS2 | Converted by Records Management Center and stored at SMS Janesville, WI. |
| VBMSRT | Location for claim folders that exist only in VBMS. |
| INVBMS | Location for claims folders that were   * established as eFolders, or * converted paper claims folders with discrepant folder location data that has been corrected. |
| EFILE | Location for claim folders that exist only in VBMS. |
| INVVA | Location for claim folders that exist in VBMS. |
| INPLCP | Location for claim folders that exist in VBMS. |
| NWXFR | Location for claim folders that exist in VBMS. |
| ICMHS | Location for claim folders that exist in VBMS. |
| SYS – NFE REASON | Location for claims folders that were established as eFolders by certain system functions or legacy application commands.    Follow instructions for resolving claims folder format discrepancies in [M21-1, Part II, Subpart ii, 1.A.2.g](#2g) when this location code is identified as the current claims folder location. |

***Important***:  Records involving claims folders scanned to the *SYS – NFE REASON* folder location are more likely to be associated with duplicate records.  These claims folders must be carefully reviewed to determine if a duplicate record exists and then appropriate duplicate record remediation procedures must be followed.

***References***:  For more information on

* resolving claims folder format discrepancies using the FOLDER LOCATION, see [M21-1, Part II, Subpart ii, 1.A.2.g](#2g), and
* duplicate record remediation, see

  + *[Duplicate Record Consolidation Materials](https://vbaw.vba.va.gov/bl/21/publicat/Users/Index.htm#bmd)*, and
  + [M21-1, Part II, Subpart ii, 1.B.3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174864/).

---

**II.ii.1.A.2.e . EP Establishment Requiring Conversion of Existing Paper Claims Folders**

Not all adjudication actions require scanning of unconverted paper claims folders.  The following end products (EPs) and EP series listed below require conversion to an eFolder:

* 010 series
* 020 series
* 030 series
* 040 series
* 095
* 110 series
* 130 series
* 140 series
* 160 series
* 290
* 295
* 310
* 320 series
* 400
* 410 series
* 420 series
* 450 series
* 510
* 511
* 512
* 680 series, and
* 930.

***Important***:  Do not request scanning of a paper claims folder if the EP is not listed above unless approved for scanning as a result of specific guidance issued by VA Central Office.

***References***:  For more information on

* circumstances under which claims processors establish the EPs referenced in this block, see [M21-4, Appendix B](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000011474/), and
* claim types that qualify for priority processing, see [M21-1, Part X, Subpart i, 1.1.a](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000177939/).

---

**II.ii.1.A.2.f . Determining if a Scanning Request Is Necessary**

Upon establishment of an EP listed in [M21-1, Part II, Subpart ii, 1.A.2.e](#2e), identify the claims folder location and use the table below to determine if a scanning request is necessary.

| **If the folder location is ...** | **Then ...** |
| --- | --- |
| an eFolder location shown in [M21-1, Part II, Subpart ii, 1.A.2.d](#2d) | the folder has already been scanned/converted to an eFolder. |
| an FRC (e.g. 010, 060, or 080) | follow the guidance on requesting claims folders from FRCs in [M21-1, Part II, Subpart ii, 3](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174868/). |

***Note***:  Review the information in [M21-1, Part II, Subpart ii, 1.A.2.g](#2g), if irregular or discrepant folder location history makes it difficult to determine if a scanning request is necessary.

***Reference***:  For more information on identifying folder locations, see the *VBMS Core User Guide*.

---

**II.ii.1.A.2.g . Resolving Claims Folder Format Discrepancies**

Claims folders that have been converted or only existed electronically may show a folder location not listed in [M21-1, Part II, Subpart ii, 1.A.2.d](#2d).  Common scenarios creating this discrepancy include

* claims brokered to another regional office, and
* claims processors accidentally receiving claims to their paper claims folder location when using legacy folder tracking applications.

When a review of the folder location does not conclusively identify the format of the claims folder, use the VBMS INTAKE tab to research shipments of claims material to scanning vendors.

The table below outlines the process of verifying shipments to a scanning site using the INTAKE tab in VBMS.

| **Step** | **Action** | |
| --- | --- | --- |
| 1 | Use the HISTORY button on the FOLDER LOCATION tab in VBMS to determine the suspected shipment date of the claim folder(s) to a scanning site. | |
| 2 | Under the INTAKE tab in VBMS   * enter the claims folder number in the FILE NUMBER field * ensure the DATE SHIPPED and DATE CREATED fields are blank * set the INTAKE SITE field to *All Intake Sites* * match the STATION field in VBMS with the station listed in the STATION column of the CLAIMS FOLDER HISTORY screen in VBMS, and * filter for results.   VBMS will display a list of each time an item was sent to scanning. | Screenshot of INTAKE tab in VBMS |
| 3 | Search the DATE CREATED column for a date corresponding with the DATE IN field in the CLAIMS FOLDER HISTORY screen.  A match verifies shipment to a scanning facility.    ***Example***: | |
| 4 | Change the incorrect folder location to INVBMS to reflect its conversion to an eFolder and apply the *VBMS* corporate flash if it has not already been added. | |

***Notes***:

* Verify all volumes were received into a scanning location.  If necessary, repeat the process for all volumes.
* Historically, VBMS claim folders required transfers via legacy applications to give the receiving station jurisdiction over the brokered claim.  Frequently, intake processing centers marked the folder received at locally-determined locations not listed in [M21-1, Part II, Subpart ii, 1.A.2.d](#2d).

***Reference***:   For more information on the intake tab and claims folder information in VBMS, see the *VBMS Core User Guide*.

---

**II.ii.1.A.2.h . Claims Folder Related Flashes**

Corporate flashes are used to indicate the claims folder format.  A combination of two or more flashes is common.  The table below provides descriptions of claims folder related flashes and when they should be applied.

| **Flash** | **Description** |
| --- | --- |
| *VBMS* | * The presence of this flash is a strong indicator that the claim folder has either    + already been electronically converted into a VBMS eFolder, or   + is in route to a scanning facility. * This flash must be added when it has been confirmed that the paper claims folder has been converted. |
| *No Paper Claim Folder* | * This flash is added when    + a claims folder is established after the implementation of VBMS, and   + a paper claims folder never existed. * Definitively establishes that the entire claims folder is the VBMS eFolder. |
| *PLCP* | * The Paperless Claims Processing (PLCP) flash was used with pre-discharge programs to indicate no paper claims folder exists. * With the implementation of VBMS for pre-discharge claims, all content is now loaded into the VBMS eFolder and this flash is no longer applied. |
| *Documents Exist in VBMS* | When only this flash displays, it indicates that there are documents located in the VBMS eFolder.    ***Note***:  This flash does not always mean that the entire claims folder is in VBMS.  It is possible even with this flash that the claims folder is still in paper format. |

---

[<-- Previous Section](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174861/)   [Next Section -->](https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000174864/)

[To Top](#top)
