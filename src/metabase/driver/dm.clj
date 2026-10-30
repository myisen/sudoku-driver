(ns metabase.driver.dm
  "Dameng (DM) database driver."
  (:require [clojure.string :as str]
            [metabase.driver :as driver]
            [metabase.driver.sql-jdbc :as sql-jdbc]
            [metabase.driver.sql-jdbc.connection :as sql-jdbc.conn]
            [metabase.driver.sql-jdbc.sync :as sql-jdbc.sync]))

(driver/register! :dm, :parent :sql-jdbc)

;;; +----------------------------------------------------------------------------------------------------------------+
;;; |                                                    connection                                                  |
;;; +----------------------------------------------------------------------------------------------------------------+

(defmethod sql-jdbc.conn/connection-details->spec :dm
  [_ {:keys [host port dbname user password]
      :or   {host "localhost", port 5236}
      :as   details}]
  (merge
   (cond-> {:classname   "dm.jdbc.driver.DmDriver"
            :subprotocol "dm"
            :subname     (str host ":" port)}
     (seq dbname)   (assoc :schema dbname)
     (seq user)     (assoc :user user)
     (seq password) (assoc :password password))
   ;; pass along any extra connection properties as-is (e.g. SSL options)
   (dissoc details :host :port :dbname :user :password)))

;;; +----------------------------------------------------------------------------------------------------------------+
;;; |                                                        sync                                                    |
;;; +----------------------------------------------------------------------------------------------------------------+

;; DM system schemas that shouldn't be surfaced in the sync process.
(defmethod sql-jdbc.sync/excluded-schemas :dm
  [_]
  #{"SYS" "SYSDBA" "SYSSSO" "SYSAUDITOR" "CTISYS"})

(def ^:private database-type->base-type
  {"BIT"                            :type/Boolean
   "BOOLEAN"                        :type/Boolean
   "TINYINT"                        :type/Integer
   "BYTE"                           :type/Integer
   "SMALLINT"                       :type/Integer
   "INT"                            :type/Integer
   "INTEGER"                        :type/Integer
   "PLS_INTEGER"                    :type/Integer
   "BIGINT"                         :type/BigInteger
   "DECIMAL"                        :type/Decimal
   "DEC"                            :type/Decimal
   "NUMERIC"                        :type/Decimal
   "NUMBER"                         :type/Number
   "FLOAT"                          :type/Float
   "DOUBLE"                         :type/Float
   "DOUBLE PRECISION"               :type/Float
   "REAL"                           :type/Float
   "CHAR"                           :type/Text
   "CHARACTER"                      :type/Text
   "VARCHAR"                        :type/Text
   "VARCHAR2"                       :type/Text
   "LONGVARCHAR"                    :type/Text
   "CLOB"                           :type/Text
   "TEXT"                           :type/Text
   "DATE"                           :type/Date
   "TIME"                           :type/Time
   "DATETIME"                       :type/DateTime
   "TIMESTAMP"                      :type/DateTime
   "TIMESTAMP WITH TIME ZONE"       :type/DateTimeWithTZ
   "TIMESTAMP WITH LOCAL TIME ZONE" :type/DateTimeWithLocalTZ
   "BINARY"                         :type/*
   "VARBINARY"                      :type/*
   "BLOB"                           :type/*
   "IMAGE"                          :type/*
   "BFILE"                          :type/*})

(defmethod sql-jdbc.sync/database-type->base-type :dm
  [_ database-type]
  (when-let [t (some-> database-type name str/upper-case)]
    (get database-type->base-type t)))
