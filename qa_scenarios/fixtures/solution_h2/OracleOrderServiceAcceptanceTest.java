package com.agentia.qa.orders.resource;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.CoreMatchers.notNullValue;

@QuarkusTest
public class OracleOrderServiceAcceptanceTest {

    @Test
    public void testOrderRecordCrudAndNotFound() {
        Integer id = given()
            .contentType("application/json")
            .body("{\"orderNumber\":\"ORD-SOL-101\",\"totalAmount\":88.25}")
            .when()
            .post("/api/orderrecord")
            .then()
            .statusCode(201)
            .body("id", notNullValue())
            .body("orderNumber", equalTo("ORD-SOL-101"))
            .extract()
            .path("id");

        given()
            .when()
            .get("/api/orderrecord/" + id)
            .then()
            .statusCode(200)
            .body("orderNumber", equalTo("ORD-SOL-101"))
            .body("totalAmount", equalTo(88.25f));

        given()
            .when()
            .delete("/api/orderrecord/" + id)
            .then()
            .statusCode(204);

        given()
            .when()
            .get("/api/orderrecord/" + id)
            .then()
            .statusCode(404);
    }
}
