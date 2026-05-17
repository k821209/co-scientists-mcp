/** Per-project API key utilities.
 *
 * v0: plaintext key stored on the /projects/{pid} doc, readable only by the
 * owner via security rules. Production: hash stored in /projects/{pid}/api_keys/{hash},
 * minted by the /create_project Cloud Function, exchanged for a Firebase custom
 * token by /exchange_key.
 *
 * Format: csk_<48 hex chars> — "co-scientist key" prefix, 24 bytes of entropy.
 */
export function generateApiKey() {
    const bytes = new Uint8Array(24);
    crypto.getRandomValues(bytes);
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    return `csk_${hex}`;
}
export function maskKey(key) {
    if (!key)
        return "—";
    if (key.length < 12)
        return key;
    return key.slice(0, 8) + "…" + key.slice(-4);
}
