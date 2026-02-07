import logging


logger = logging.getLogger("pytest_results")


def pytest_runtest_logreport(report):
    if report.when == "call":
        logger.info("TEST %s - %s", report.nodeid, report.outcome)


def pytest_sessionfinish(session, exitstatus):
    logger.info("PYTEST_SESSION_END status=%s failed=%s", exitstatus, session.testsfailed)
