# Dockerfile for Policy Gateway (Rust)

FROM rust:1.75-slim as builder

WORKDIR /app

# Copy manifests
COPY Cargo.toml Cargo.lock ./
COPY src ./src

# Build release binary
RUN cargo build --release

# Runtime image
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/target/release/policy_gateway /app/policy_gateway

# Create non-root user
RUN useradd -r -s /bin/false appuser
USER appuser

EXPOSE 8080

ENV RUST_LOG=info

CMD ["/app/policy_gateway"]
