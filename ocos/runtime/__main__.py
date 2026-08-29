"""
OCOS Runtime — Phase 39.1 Skeleton.

    python -m ocos.runtime

Boots the RuntimeKernel, runs 60 ticks (with checkpoint every 10),
shuts down gracefully, then prints the checkpoint path.
"""

from .runtime_kernel import RuntimeKernel


def main():
    kernel = RuntimeKernel()
    runtime_id = kernel.start()
    print(f"Runtime BOOT: {runtime_id}")
    print(f"State: {kernel.state.value}")

    kernel.tick_loop(max_ticks=60)
    print(f"Ticks completed: {kernel.tick_count}")
    print(f"Last tick: {kernel.last_tick_id}")

    kernel.shutdown(checkpoint=True)
    print(f"State: {kernel.state.value}")
    print(f"Checkpoint saved at tick {kernel.last_tick_id}")


if __name__ == "__main__":
    main()
