/* SPDX-License-Identifier: Apache-2.0 */
#include "qsl/order_book.h"

#include <string.h>

_Static_assert(QSL_MAX_ORDERS <= UINT64_MAX / UINT32_MAX,
               "Aggregated quantity must fit in uint64_t");

void qsl_book_init(qsl_book *book)
{
    if (book != NULL) {
        memset(book, 0, sizeof(*book));
    }
}

static size_t find_order(const qsl_book *book, uint64_t id)
{
    for (size_t i = 0; i < QSL_MAX_ORDERS; ++i) {
        if (book->orders[i].remaining != 0 && book->orders[i].id == id) {
            return i;
        }
    }
    return QSL_MAX_ORDERS;
}

qsl_status qsl_book_apply(qsl_book *book, const qsl_event *event)
{
    if (book == NULL || event == NULL || event->id == 0) {
        return QSL_INVALID;
    }
    if (event->type != QSL_ADD && event->type != QSL_CANCEL &&
        event->type != QSL_EXECUTE && event->type != QSL_DELETE) {
        return QSL_INVALID;
    }
    if (event->type == QSL_ADD) {
        if ((event->side != QSL_BUY && event->side != QSL_SELL) ||
            event->price == 0 || event->quantity == 0) {
            return QSL_INVALID;
        }
        if (find_order(book, event->id) != QSL_MAX_ORDERS) {
            return QSL_DUPLICATE_ID;
        }
        for (size_t i = 0; i < QSL_MAX_ORDERS; ++i) {
            if (book->orders[i].remaining == 0) {
                book->orders[i] = (qsl_order){
                    .id = event->id, .price = event->price,
                    .remaining = event->quantity, .side = event->side
                };
                return QSL_OK;
            }
        }
        return QSL_FULL;
    }
    if (event->type != QSL_DELETE && event->quantity == 0) {
        return QSL_INVALID;
    }
    size_t index = find_order(book, event->id);
    if (index == QSL_MAX_ORDERS) {
        return QSL_NOT_FOUND;
    }
    qsl_order *order = &book->orders[index];
    if (event->type == QSL_DELETE) {
        memset(order, 0, sizeof(*order));
        return QSL_OK;
    }
    if (event->quantity > order->remaining) {
        return QSL_EXCESS_QUANTITY;
    }
    order->remaining -= event->quantity;
    if (order->remaining == 0) {
        memset(order, 0, sizeof(*order));
    }
    return QSL_OK;
}

qsl_status qsl_book_quote(const qsl_book *book, qsl_quote *quote)
{
    if (book == NULL || quote == NULL) {
        return QSL_INVALID;
    }
    memset(quote, 0, sizeof(*quote));
    for (size_t i = 0; i < QSL_MAX_ORDERS; ++i) {
        const qsl_order *order = &book->orders[i];
        if (order->remaining == 0) {
            continue;
        }
        ++quote->active_orders;
        if (order->side == QSL_BUY) {
            if (!quote->has_bid || order->price > quote->bid_price) {
                quote->has_bid = true;
                quote->bid_price = order->price;
                quote->bid_quantity = order->remaining;
            } else if (order->price == quote->bid_price) {
                quote->bid_quantity += order->remaining;
            }
        } else {
            if (!quote->has_ask || order->price < quote->ask_price) {
                quote->has_ask = true;
                quote->ask_price = order->price;
                quote->ask_quantity = order->remaining;
            } else if (order->price == quote->ask_price) {
                quote->ask_quantity += order->remaining;
            }
        }
    }
    return QSL_OK;
}

bool qsl_quote_spread(const qsl_quote *quote, int64_t *spread)
{
    if (quote == NULL || spread == NULL || !quote->has_bid || !quote->has_ask) {
        return false;
    }
    *spread = (int64_t)quote->ask_price - (int64_t)quote->bid_price;
    return true;
}
