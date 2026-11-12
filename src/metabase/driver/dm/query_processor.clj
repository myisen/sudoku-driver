(ns metabase.driver.dm.query-processor
  "DM (Dameng) query processor extensions. DM is largely Oracle-compatible for date truncation/extract, and
  SQL Server-compatible for DATEADD/DATEDIFF date arithmetic."
  (:require
   [metabase.driver.sql.query-processor :as sql.qp]
   [metabase.util.honey-sql-2 :as h2x]))

(defn- trunc
  "Truncate a date to a certain level, e.g. (trunc \"mi\" expr) -> TRUNC(expr, 'mi')."
  [format-str expr]
  (-> [:trunc expr (h2x/literal format-str)]
      ;; TRUNC() returns a DATE
      (h2x/with-database-type-info "date")))

(defmethod sql.qp/date [:dm :default]         [_ _ expr] expr)
(defmethod sql.qp/date [:dm :minute]          [_ _ expr] (trunc "mi" expr))
(defmethod sql.qp/date [:dm :minute-of-hour]  [_ _ expr] [::h2x/extract :minute (h2x/->timestamp expr)])
(defmethod sql.qp/date [:dm :hour]            [_ _ expr] (trunc "hh" expr))
(defmethod sql.qp/date [:dm :hour-of-day]     [_ _ expr] [::h2x/extract :hour (h2x/->timestamp expr)])
(defmethod sql.qp/date [:dm :day]             [_ _ expr] (trunc "dd" expr))
(defmethod sql.qp/date [:dm :day-of-month]    [_ _ expr] [::h2x/extract :day expr])
(defmethod sql.qp/date [:dm :day-of-year]     [_ _ expr] (h2x/->integer [:to_number [:to_char expr (h2x/literal "DDD")]]))
(defmethod sql.qp/date [:dm :month]           [_ _ expr] (trunc "mm" expr))
(defmethod sql.qp/date [:dm :month-of-year]   [_ _ expr] [::h2x/extract :month expr])
(defmethod sql.qp/date [:dm :quarter]         [_ _ expr] (trunc "q" expr))
(defmethod sql.qp/date [:dm :quarter-of-year] [_ _ expr] (h2x/->integer [:to_char expr (h2x/literal "Q")]))
(defmethod sql.qp/date [:dm :year]            [_ _ expr] (trunc "yyyy" expr))

(defmethod sql.qp/date [:dm :week]
  [driver _ expr]
  (sql.qp/adjust-start-of-week driver (partial trunc "day") expr))

;; DM `TO_CHAR(date, 'D')` returns 1 = Sunday ... 7 = Saturday, which matches the Metabase default
;; (db-start-of-week :sunday).
(defmethod sql.qp/date [:dm :day-of-week]
  [_ _ expr]
  (h2x/->integer [:to_char expr (h2x/literal "D")]))

;;; +----------------------------------------------------------------------------------------------------------------+
;;; |                                                 date arithmetic                                                |
;;; +----------------------------------------------------------------------------------------------------------------+

;; DM DATEADD/DATEDIFF datepart tokens (SQL Server style): yy qq mm wk dd hh mi ss ms.
(def ^:private date-add-units
  {:year "yy", :quarter "qq", :month "mm", :week "wk", :day "dd"
   :hour "hh", :minute "mi", :second "ss", :millisecond "ms"})

(defn- maybe-inline-number
  "Inline numbers so DATEADD doesn't get a prepared-statement parameter for its amount."
  [x]
  (if (number? x) [:inline x] x))

(defn- date-add [datepart amount expr]
  [:dateadd [:raw (name datepart)] (maybe-inline-number amount) expr])

(defn- date-diff [datepart x y]
  [:datediff [:raw (name datepart)] x y])

(defmethod sql.qp/add-interval-honeysql-form :dm
  [_ hsql-form amount unit]
  (date-add (get date-add-units unit) amount hsql-form))

(defmethod sql.qp/unix-timestamp->honeysql [:dm :seconds]
  [_driver _unit expr]
  (date-add "ss" expr (h2x/literal "1970-01-01 00:00:00")))

(defmethod sql.qp/unix-timestamp->honeysql [:dm :milliseconds]
  [driver _unit expr]
  (sql.qp/unix-timestamp->honeysql driver :seconds (h2x// expr [:inline 1000])))

(defmethod sql.qp/datetime-diff [:dm :year]
  [driver _unit x y]
  (h2x// (sql.qp/datetime-diff driver :month x y) 12))

(defmethod sql.qp/datetime-diff [:dm :quarter]
  [driver _unit x y]
  (h2x// (sql.qp/datetime-diff driver :month x y) 3))

(defmethod sql.qp/datetime-diff [:dm :month]
  [_driver _unit x y]
  (h2x/+ (date-diff "mm" x y)
         ;; DATEDIFF counts month boundaries, not whole months, so adjust:
         ;; if x<y but x>y in the month calendar then subtract one month
         ;; if x>y but x<y in the month calendar then add one month
         [:case
          [:and [:< x y] [:> (h2x/day x) (h2x/day y)]] -1
          [:and [:> x y] [:< (h2x/day x) (h2x/day y)]] 1
          :else 0]))

(defmethod sql.qp/datetime-diff [:dm :week]   [_driver _unit x y] (h2x// (date-diff "dd" x y) 7))
(defmethod sql.qp/datetime-diff [:dm :day]    [_driver _unit x y] (date-diff "dd" x y))
(defmethod sql.qp/datetime-diff [:dm :hour]   [_driver _unit x y] (date-diff "hh" x y))
(defmethod sql.qp/datetime-diff [:dm :minute] [_driver _unit x y] (date-diff "mi" x y))
(defmethod sql.qp/datetime-diff [:dm :second] [_driver _unit x y] (date-diff "ss" x y))
