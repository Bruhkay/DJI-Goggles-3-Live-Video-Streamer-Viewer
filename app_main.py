"""Entry point of the packaged app.

The same executable is started twice: once as the window, and once (with
--helper, possibly as root) as the USB helper process.
"""
import sys

if __name__ == "__main__":
    if "--helper" in sys.argv:
        from g3.helper import main as helper_main
        i = sys.argv.index("--helper")
        sys.exit(helper_main(sys.argv[i + 1:]))
    from g3.app import main
    sys.exit(main())
