export async function sendMessage(
    apiPort,
    destination,
    payload
) {

    try {

        const response = await fetch(
            `http://localhost:${apiPort}/send`,
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    destination,
                    payload
                })
            }
        )

        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            )

        }

        return await response.json()

    } catch (error) {

        console.error(
            "Send Message Error",
            error
        )

        return {
            success: false,
            error: error.message
        }

    }
}