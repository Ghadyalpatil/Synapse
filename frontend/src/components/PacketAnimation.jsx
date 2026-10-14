import { motion, AnimatePresence } from "framer-motion";

export default function PacketAnimation({
    sending
}) {

    if (!sending) return null;

    return (

        <AnimatePresence>

            <motion.div

                initial={{
                    x: 0,
                    y: 0,
                    opacity: 1
                }}

                animate={{

                    x: [
                        0,
                        260,
                        520,
                        780
                    ],

                    y: [
                        0,
                        0,
                        0,
                        0
                    ]
                }}

                transition={{
                    duration: 4,
                    ease: "linear"
                }}

                exit={{
                    opacity: 0
                }}

                style={{

                    position: "absolute",

                    left: "160px",
                    top: "185px",

                    width: "20px",
                    height: "20px",

                    borderRadius: "50%",

                    background:
                        "radial-gradient(circle,#00ff88,#00e5ff)",

                    boxShadow:
                        `
                        0 0 10px #00ff88,
                        0 0 20px #00ff88,
                        0 0 40px #00e5ff
                        `,

                    zIndex: 9999
                }}
            />

        </AnimatePresence>
    );
}