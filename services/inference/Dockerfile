FROM gradle:8.8-jdk21 AS build

WORKDIR /app
COPY build.gradle.kts settings.gradle.kts ./
RUN gradle dependencies --no-daemon
COPY src ./src
RUN gradle bootJar --no-daemon

FROM eclipse-temurin:21-jre-alpine

RUN addgroup -S appuser && adduser -S appuser -G appuser
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar
USER appuser
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
