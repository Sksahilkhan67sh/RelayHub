package dev.relayhub.sdk;

public final class AuthResource {
    private final Transport transport;

    AuthResource(Transport transport) { this.transport = transport; }

    public static final class RegisterRequest {
        public String email, password, fullName, organizationName;
        public RegisterRequest(String email, String password, String fullName, String organizationName) {
            this.email = email; this.password = password; this.fullName = fullName; this.organizationName = organizationName;
        }
    }

    /** POST /v1/auth/register */
    public Models.TokenResponse register(RegisterRequest req) { return register(req, null); }
    public Models.TokenResponse register(RegisterRequest req, RequestOptions options) {
        return transport.request("POST", "/v1/auth/register", req, Models.TokenResponse.class, options);
    }

    /** POST /v1/auth/login */
    public Models.TokenResponse login(String email, String password) { return login(email, password, null); }
    public Models.TokenResponse login(String email, String password, RequestOptions options) {
        return transport.request("POST", "/v1/auth/login", java.util.Map.of("email", email, "password", password), Models.TokenResponse.class, options);
    }

    /** POST /v1/auth/refresh */
    public Models.TokenResponse refresh(String refreshToken) { return refresh(refreshToken, null); }
    public Models.TokenResponse refresh(String refreshToken, RequestOptions options) {
        return transport.request("POST", "/v1/auth/refresh", java.util.Map.of("refresh_token", refreshToken), Models.TokenResponse.class, options);
    }

    /** POST /v1/auth/logout -- 204 No Content on success. */
    public void logout() { logout(null); }
    public void logout(RequestOptions options) {
        transport.request("POST", "/v1/auth/logout", null, Void.class, options);
    }

    /** GET /v1/auth/me */
    public Models.MeResponse me() { return me(null); }
    public Models.MeResponse me(RequestOptions options) {
        return transport.request("GET", "/v1/auth/me", null, Models.MeResponse.class, options);
    }

    /** POST /v1/auth/forgot-password -- always returns the same generic message whether or not the email is registered, by design. */
    public String forgotPassword(String email) { return forgotPassword(email, null); }
    public String forgotPassword(String email, RequestOptions options) {
        var resp = transport.request("POST", "/v1/auth/forgot-password", java.util.Map.of("email", email), java.util.Map.class, options);
        Object message = resp != null ? resp.get("message") : null;
        return message != null ? message.toString() : null;
    }

    /** POST /v1/auth/reset-password -- 204 No Content on success. */
    public void resetPassword(String token, String newPassword) { resetPassword(token, newPassword, null); }
    public void resetPassword(String token, String newPassword, RequestOptions options) {
        transport.request("POST", "/v1/auth/reset-password", java.util.Map.of("token", token, "new_password", newPassword), Void.class, options);
    }
}
