/* SPDX-License-Identifier: Apache-2.0 */
#ifndef QSL_ORDER_BOOK_H
#define QSL_ORDER_BOOK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define QSL_MAX_ORDERS 64u

typedef enum { QSL_BUY = 1, QSL_SELL = 2 } qsl_side;
typedef enum { QSL_ADD = 1, QSL_CANCEL, QSL_EXECUTE, QSL_DELETE } qsl_event_type;
typedef enum {
    QSL_OK = 0,
    QSL_INVALID,
    QSL_DUPLICATE_ID,
    QSL_NOT_FOUND,
    QSL_FULL,
    QSL_EXCESS_QUANTITY
} qsl_status;

typedef struct {
    uint64_t id;
    uint32_t price;
    uint32_t remaining; /* Zero marks an unused slot. */
    qsl_side side;
} qsl_order;

typedef struct {
    qsl_order orders[QSL_MAX_ORDERS];
} qsl_book;

typedef struct {
    qsl_event_type type;
    uint64_t id;
    qsl_side side;   /* Used only by ADD. */
    uint32_t price;  /* Used only by ADD. Integer price units. */
    uint32_t quantity; /* Used by ADD, CANCEL and EXECUTE. */
} qsl_event;

typedef struct {
    bool has_bid;
    bool has_ask;
    uint32_t bid_price;
    uint32_t ask_price;
    uint64_t bid_quantity;
    uint64_t ask_quantity;
    size_t active_orders;
} qsl_quote;

/* Initialize before use. NULL is a no-op. Treat book storage as read-only
 * outside this API. The reference implementation performs no allocation. */
void qsl_book_init(qsl_book *book);

/* Rejected events leave the book unchanged. Single instrument, single thread.
 * CANCEL/EXECUTE reduce the named order; DELETE removes it completely. */
qsl_status qsl_book_apply(qsl_book *book, const qsl_event *event);
qsl_status qsl_book_quote(const qsl_book *book, qsl_quote *quote);

/* False if either side is missing or arguments are NULL; output is untouched.
 * Negative spreads are possible: reconstruction does not perform matching. */
bool qsl_quote_spread(const qsl_quote *quote, int64_t *spread);

#endif
