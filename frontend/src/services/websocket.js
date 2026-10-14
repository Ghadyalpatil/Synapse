export function connectWebSocket(port, callback) {

    const socket = new WebSocket(
        `ws://localhost:${port}`
    )

    socket.onopen = () => {
        console.log(
            `Connected to WS ${port}`
        )
    }

    socket.onmessage = (event) => {
        try {

            const data = JSON.parse(
                event.data
            )

            callback(data)

        } catch (err) {

            console.error(
                "WebSocket Parse Error",
                err
            )

        }
    }

    socket.onerror = (error) => {

        console.error(
            "WebSocket Error",
            error
        )

    }

    socket.onclose = () => {

        console.log(
            `WS ${port} closed`
        )

    }

    return socket
}