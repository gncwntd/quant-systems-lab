/* SPDX-License-Identifier: Apache-2.0 */
#include "qsl/order_book.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); \
        exit(EXIT_FAILURE); \
    } \
} while (0)

static void apply(qsl_book *book, qsl_event event)
{
    CHECK(qsl_book_apply(book, &event) == QSL_OK);
}

static qsl_quote quote(const qsl_book *book)
{
    qsl_quote result;
    CHECK(qsl_book_quote(book, &result) == QSL_OK);
    return result;
}

static void rejected(qsl_book *book, qsl_event event, qsl_status expected)
{
    unsigned char before[sizeof(*book)];
    memcpy(before, book, sizeof(*book));
    CHECK(qsl_book_apply(book, &event) == expected);
    CHECK(memcmp(before, book, sizeof(*book)) == 0);
}

static void scenario(void)
{
    qsl_book book;
    qsl_book_init(&book);
    qsl_quote q = quote(&book);
    int64_t spread = 123;
    CHECK(!q.has_bid && !q.has_ask && q.active_orders == 0);
    CHECK(!qsl_quote_spread(&q, &spread) && spread == 123);
    apply(&book, (qsl_event){QSL_ADD, 101, QSL_BUY, 10000, 10});
    q = quote(&book);
    CHECK(q.has_bid && !q.has_ask && q.bid_quantity == 10);
    CHECK(!qsl_quote_spread(&q, &spread) && spread == 123);
    apply(&book, (qsl_event){QSL_ADD, 102, QSL_BUY, 10000, 6});
    apply(&book, (qsl_event){QSL_ADD, 201, QSL_SELL, 10002, 8});
    q = quote(&book);
    CHECK(q.bid_quantity == 16 && q.ask_quantity == 8 && q.active_orders == 3);
    CHECK(qsl_quote_spread(&q, &spread) && spread == 2);
    apply(&book, (qsl_event){QSL_CANCEL, 101, 0, 0, 4});
    apply(&book, (qsl_event){QSL_EXECUTE, 201, 0, 0, 3});
    q = quote(&book);
    CHECK(q.bid_quantity == 12 && q.ask_quantity == 5);
    apply(&book, (qsl_event){QSL_DELETE, 102, 0, 0, 0});
    q = quote(&book);
    CHECK(q.bid_quantity == 6 && q.ask_quantity == 5 && q.active_orders == 2);
    apply(&book, (qsl_event){QSL_ADD, 103, QSL_BUY, 9998, 7});
    CHECK(quote(&book).bid_price == 10000);
    apply(&book, (qsl_event){QSL_DELETE, 101, 0, 0, 0});
    q = quote(&book);
    CHECK(q.bid_price == 9998 && q.bid_quantity == 7 && q.ask_price == 10002);
    CHECK(qsl_quote_spread(&q, &spread) && spread == 4);
    apply(&book, (qsl_event){QSL_EXECUTE, 201, 0, 0, 5});
    q = quote(&book);
    CHECK(!q.has_ask && q.ask_quantity == 0 && q.active_orders == 1);
    CHECK(!qsl_quote_spread(&q, &spread));
    apply(&book, (qsl_event){QSL_CANCEL, 103, 0, 0, 7});
    CHECK(quote(&book).active_orders == 0);
}

static void errors(void)
{
    qsl_book book;
    qsl_book_init(&book);
    apply(&book, (qsl_event){QSL_ADD, 1, QSL_BUY, 100, 6});
    rejected(&book, (qsl_event){QSL_ADD, 1, QSL_SELL, 101, 1}, QSL_DUPLICATE_ID);
    rejected(&book, (qsl_event){QSL_ADD, 0, QSL_BUY, 100, 1}, QSL_INVALID);
    rejected(&book, (qsl_event){QSL_ADD, 2, 0, 100, 1}, QSL_INVALID);
    rejected(&book, (qsl_event){QSL_ADD, 2, QSL_BUY, 0, 1}, QSL_INVALID);
    rejected(&book, (qsl_event){QSL_ADD, 2, QSL_BUY, 100, 0}, QSL_INVALID);
    rejected(&book, (qsl_event){(qsl_event_type)99, 1, 0, 0, 1}, QSL_INVALID);
    rejected(&book, (qsl_event){QSL_CANCEL, 1, 0, 0, 0}, QSL_INVALID);
    rejected(&book, (qsl_event){QSL_EXECUTE, 1, 0, 0, 7}, QSL_EXCESS_QUANTITY);
    rejected(&book, (qsl_event){QSL_CANCEL, 1, 0, 0, 7}, QSL_EXCESS_QUANTITY);
    rejected(&book, (qsl_event){QSL_DELETE, 2, 0, 0, 0}, QSL_NOT_FOUND);
    rejected(&book, (qsl_event){QSL_EXECUTE, 2, 0, 0, 1}, QSL_NOT_FOUND);
    CHECK(qsl_book_apply(NULL, NULL) == QSL_INVALID);
    CHECK(qsl_book_apply(&book, NULL) == QSL_INVALID);
    CHECK(qsl_book_quote(&book, NULL) == QSL_INVALID);
    qsl_quote q;
    CHECK(qsl_book_quote(NULL, &q) == QSL_INVALID);
    CHECK(!qsl_quote_spread(NULL, NULL));
}

static void capacity(void)
{
    qsl_book book;
    qsl_book_init(&book);
    for (size_t i = 0; i < QSL_MAX_ORDERS; ++i) {
        apply(&book, (qsl_event){QSL_ADD, (uint64_t)i + 1, QSL_BUY, 100, UINT32_MAX});
    }
    qsl_quote q = quote(&book);
    CHECK(q.active_orders == QSL_MAX_ORDERS);
    CHECK(q.bid_quantity == (uint64_t)QSL_MAX_ORDERS * UINT32_MAX);
    rejected(&book, (qsl_event){QSL_ADD, 1000, QSL_BUY, 100, 1}, QSL_FULL);
    apply(&book, (qsl_event){QSL_DELETE, 1, 0, 0, 0});
    apply(&book, (qsl_event){QSL_ADD, 1000, QSL_SELL, 101, 1});
    CHECK(quote(&book).active_orders == QSL_MAX_ORDERS);
    apply(&book, (qsl_event){QSL_DELETE, 1000, 0, 0, 0});
    apply(&book, (qsl_event){QSL_ADD, 1, QSL_BUY, 99, 1});
    CHECK(quote(&book).active_orders == QSL_MAX_ORDERS);
}

static void limits(void)
{
    qsl_book book;
    qsl_book_init(&book);
    apply(&book, (qsl_event){QSL_ADD, UINT64_MAX, QSL_BUY, UINT32_MAX, 1});
    apply(&book, (qsl_event){QSL_ADD, 1, QSL_SELL, 1, 2});
    apply(&book, (qsl_event){QSL_ADD, 2, QSL_SELL, 1, 3});
    apply(&book, (qsl_event){QSL_ADD, 3, QSL_SELL, 2, 10});
    qsl_quote q = quote(&book);
    int64_t spread;
    CHECK(q.ask_price == 1 && q.ask_quantity == 5);
    CHECK(qsl_quote_spread(&q, &spread) && spread == 1 - (int64_t)UINT32_MAX);
    apply(&book, (qsl_event){QSL_DELETE, 1, 0, 0, 0});
    CHECK(quote(&book).ask_quantity == 3);
    apply(&book, (qsl_event){QSL_DELETE, 2, 0, 0, 0});
    CHECK(quote(&book).ask_price == 2 && quote(&book).ask_quantity == 10);
    CHECK(!qsl_quote_spread(&q, NULL));
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        return EXIT_FAILURE;
    }
    if (strcmp(argv[1], "scenario") == 0) {
        scenario();
    } else if (strcmp(argv[1], "errors") == 0) {
        errors();
    } else if (strcmp(argv[1], "capacity") == 0) {
        capacity();
    } else if (strcmp(argv[1], "limits") == 0) {
        limits();
    } else {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
