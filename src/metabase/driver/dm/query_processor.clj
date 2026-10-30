(ns metabase.driver.dm.query-processor
  "DM (Dameng) query processor extensions. DM is largely Oracle-compatible, so date truncation/extract follows the
  same approach as the Oracle driver."
  (:require [metabase.driver.sql.query-processor :as sql.qp]
            [metabase.util.honeysql-extensions :as hx]))

(defn- trunc
  "Truncate a date/timestamp to a certain level, e.g. (trunc \"mi\" expr)."
  [format-str expr]
  (hx/call :trunc expr (hx/literal format-str)))

(defmethod sql.qp/date [:dm :default]         [_ _ expr] expr)
(defmethod sql.qp/date [:dm :minute]          [_ _ expr] (trunc "mi" expr))
(defmethod sql.qp/date [:dm :minute-of-hour]  [_ _ expr] (hx/->integer (hx/call :extract :minute expr)))
(defmethod sql.qp/date [:dm :hour]            [_ _ expr] (trunc "hh" expr))
(defmethod sql.qp/date [:dm :hour-of-day]     [_ _ expr] (hx/->integer (hx/call :extract :hour expr)))
(defmethod sql.qp/date [:dm :day]             [_ _ expr] (trunc "dd" expr))
(defmethod sql.qp/date [:dm :day-of-month]    [_ _ expr] (hx/->integer (hx/call :extract :day expr)))
(defmethod sql.qp/date [:dm :day-of-year]     [_ _ expr] (hx/->integer (hx/call :to_number (hx/call :to_char expr (hx/literal "DDD")))))
(defmethod sql.qp/date [:dm :month]           [_ _ expr] (trunc "mm" expr))
(defmethod sql.qp/date [:dm :month-of-year]   [_ _ expr] (hx/->integer (hx/call :extract :month expr)))
(defmethod sql.qp/date [:dm :quarter]         [_ _ expr] (trunc "q" expr))
(defmethod sql.qp/date [:dm :quarter-of-year] [_ _ expr] (hx/->integer (hx/call :to_number (hx/call :to_char expr (hx/literal "Q")))))
(defmethod sql.qp/date [:dm :year]            [_ _ expr] (trunc "yyyy" expr))

;; DM `TO_CHAR(date, 'D')` returns 1 = Sunday ... 7 = Saturday, which matches the Metabase default.
(defmethod sql.qp/date [:dm :day-of-week] [_ _ expr]
  (hx/->integer (hx/call :to_char expr (hx/literal "D"))))

(defmethod sql.qp/date [:dm :week] [_ _ expr]
  (trunc "iw" expr))

(defmethod sql.qp/unix-timestamp->timestamp [:dm :seconds]
  [_ _ expr]
  (hx/call :dateadd (hx/literal "ss") expr (hx/literal "1970-01-01 00:00:00")))

(defmethod sql.qp/unix-timestamp->timestamp [:dm :milliseconds]
  [_ _ expr]
  (hx/call :dateadd (hx/literal "ss") (hx// expr 1000) (hx/literal "1970-01-01 00:00:00")))
