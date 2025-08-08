-- SQL Migration Script from old schema to new schema
--
-- This script is designed to be run once.
-- It is recommended to backup your database before running this script.
--

-- Step 1: Create the new tables

CREATE TABLE `Clients` (
  `Id` int NOT NULL AUTO_INCREMENT,
  `Phone` varchar(255) DEFAULT NULL,
  `Mobile` varchar(255) DEFAULT NULL,
  `Email` varchar(255) DEFAULT NULL,
  `FirstName` varchar(255) DEFAULT NULL,
  `LastName` varchar(255) DEFAULT NULL,
  `Title` varchar(255) DEFAULT NULL,
  `Address` varchar(255) DEFAULT NULL,
  `City` varchar(255) DEFAULT NULL,
  `Status` varchar(255) DEFAULT NULL,
  `IsArchived` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`Id`)
);

CREATE TABLE `Companies` (
  `Id` int NOT NULL AUTO_INCREMENT,
  `Name` varchar(255) DEFAULT NULL,
  `PhoneNumber` varchar(255) DEFAULT NULL,
  `Email` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`Id`)
);

CREATE TABLE `Formulas` (
  `Id` int NOT NULL AUTO_INCREMENT,
  `Name` varchar(255) DEFAULT NULL,
  `Description` text,
  `Price` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`Id`)
);

CREATE TABLE `Contracts` (
  `Id` int NOT NULL AUTO_INCREMENT,
  `ClientId` int DEFAULT NULL,
  `Reference` varchar(255) DEFAULT NULL,
  `Status` varchar(255) DEFAULT NULL,
  `Price` decimal(10,2) DEFAULT NULL,
  `Amount` decimal(10,2) DEFAULT NULL,
  `EffectiveDate` date DEFAULT NULL,
  `TerminationDate` date DEFAULT NULL,
  `CompanyId` int DEFAULT NULL,
  `FormulaId` int DEFAULT NULL,
  PRIMARY KEY (`Id`),
  KEY `ClientId` (`ClientId`),
  KEY `CompanyId` (`CompanyId`),
  KEY `FormulaId` (`FormulaId`),
  CONSTRAINT `contracts_ibfk_1` FOREIGN KEY (`ClientId`) REFERENCES `Clients` (`Id`),
  CONSTRAINT `contracts_ibfk_2` FOREIGN KEY (`CompanyId`) REFERENCES `Companies` (`Id`),
  CONSTRAINT `contracts_ibfk_3` FOREIGN KEY (`FormulaId`) REFERENCES `Formulas` (`Id`)
);

CREATE TABLE `ClientEventsHistory` (
  `Id` int NOT NULL AUTO_INCREMENT,
  `ClientId` int DEFAULT NULL,
  `ForDate` datetime DEFAULT NULL,
  `Comment` text,
  `IsCompleted` tinyint(1) DEFAULT '0',
  `EventId` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`Id`),
  KEY `ClientId` (`ClientId`),
  CONSTRAINT `clienteventshistory_ibfk_1` FOREIGN KEY (`ClientId`) REFERENCES `Clients` (`Id`)
);

CREATE TABLE `AspNetUsers` (
  `Id` int NOT NULL AUTO_INCREMENT,
  `FirstName` varchar(255) DEFAULT NULL,
  `LastName` varchar(255) DEFAULT NULL,
  `NickName` varchar(255) DEFAULT NULL,
  `Function` varchar(255) DEFAULT NULL,
  `IsActive` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`Id`)
);

CREATE TABLE `AdvisoryDuties` (
  `Id` int NOT NULL AUTO_INCREMENT,
  `ClientId` int DEFAULT NULL,
  `ClientSituation` text,
  `Budget` varchar(255) DEFAULT NULL,
  `Need1` text,
  `Need2` text,
  `Need3` text,
  `SelectedCompany` varchar(255) DEFAULT NULL,
  `ProvidentCompanyId` int DEFAULT NULL,
  PRIMARY KEY (`Id`),
  KEY `ClientId` (`ClientId`),
  CONSTRAINT `advisoryduties_ibfk_1` FOREIGN KEY (`ClientId`) REFERENCES `Clients` (`Id`)
);


-- Step 2: Rename old tables for backup

ALTER TABLE `adherents` RENAME TO `adherents_old`;
ALTER TABLE `formules` RENAME TO `formules_old`;
ALTER TABLE `contrats` RENAME TO `contrats_old`;
ALTER TABLE `garanties` RENAME TO `garanties_old`;
ALTER TABLE `formules_garanties` RENAME TO `formules_garanties_old`;
ALTER TABLE `sinistres_artex` RENAME TO `sinistres_artex_old`;


-- Step 3: Migrate data from old tables to new tables

INSERT INTO `Clients` (`Id`, `Phone`, `Mobile`, `Email`, `FirstName`, `LastName`, `Address`, `City`, `Status`)
SELECT `id_adherent`, `telephone`, `telephone`, `email`, `prenom`, `nom`, `adresse`, `ville`, 'Actif'
FROM `adherents_old`;

INSERT INTO `Formulas` (`Id`, `Name`, `Description`, `Price`)
SELECT `id_formule`, `nom_formule`, `description_formule`, `tarif_base_mensuel`
FROM `formules_old`;

INSERT INTO `Contracts` (`Id`, `ClientId`, `Reference`, `Status`, `EffectiveDate`, `TerminationDate`, `FormulaId`)
SELECT `id_contrat`, `id_adherent_principal`, `numero_contrat`, `statut_contrat`, `date_debut_contrat`, `date_fin_contrat`, `id_formule`
FROM `contrats_old`;

INSERT INTO `ClientEventsHistory` (`ClientId`, `ForDate`, `Comment`, `EventId`)
SELECT `id_adherent`, `date_survenance`, `description_sinistre`, `type_sinistre`
FROM `sinistres_artex_old`;

-- Note: No data migration for AspNetUsers, Companies, and AdvisoryDuties as they are new tables.

-- Step 4: (Optional) Drop old tables after verifying data migration
--
-- DROP TABLE `adherents_old`;
-- DROP TABLE `formules_old`;
-- DROP TABLE `contrats_old`;
-- DROP TABLE `garanties_old`;
-- DROP TABLE `formules_garanties_old`;
-- DROP TABLE `sinistres_artex_old`;

-- End of migration script.
