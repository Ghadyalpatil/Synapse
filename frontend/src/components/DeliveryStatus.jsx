export default function DeliveryStatus({events}) {
    const delivered = events.filter((event) => event.type === 'MESSAGE_DELIVERED')
    return (
        <div className="border p-4 rounded-xl">
            <h2>DeliveryConfirmation</h2>
            {delivered.map((event, index) => (
                <div key={index}>
                    Delivered to: {event.destination}
                </div>
            ))}
        </div>
    )
}